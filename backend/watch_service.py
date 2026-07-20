# =============================================================================
# watch_service.py -- Phase 4: Real-Time Watch Mode.
#
# Watches a local folder (via the `watchdog` filesystem-events library) and
# automatically re-runs the EXISTING scan pipeline (scan_service.run_and_store_scan,
# unchanged) whenever a tracked source file is created, modified, or deleted.
# Purely additive: every rescan is a normal ScanRecord row tagged with this
# session's batch_id, so a watch session is automatically browsable afterwards
# via Project Scanner / Dependency Graph / History, exactly like any other
# batch scan -- no new schema.
#
# Delivered as short-interval REST polling rather than a WebSocket: this repo
# has no existing WebSocket infrastructure (and the Vite dev proxy isn't
# configured for `ws: true`), so polling is the lower-risk way to get the
# same "live" behaviour without introducing a new, harder-to-verify transport.
# =============================================================================

import os
import time
import uuid
import threading
import collections
import datetime as dt

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from database import SessionLocal, ScanRecord
from scan_service import run_and_store_scan
from routers.scan import CODE_EXTENSIONS, EXCLUDED_DIR_NAMES

_LOCK = threading.Lock()
_SESSIONS = {}  # session_id -> session dict
_SETTLE_SECONDS = 0.6  # wait for the write burst (created+modified, or multiple flushes) to go quiet
_READ_RETRIES = 4
_READ_RETRY_DELAY = 0.15


def _new_session_id():
    return "watch_" + uuid.uuid4().hex[:10]


class _Handler(FileSystemEventHandler):
    """
    A single filesystem write (especially editors doing atomic save, or a
    heredoc/redirect doing create+write+close) fires MULTIPLE raw watchdog
    events in quick succession, and the file can still be mid-write /
    transiently locked when the first event arrives. Rather than reading
    immediately, each event (re)starts a short per-path settle timer; the
    actual scan only runs once no further events arrive for that path for
    `_SETTLE_SECONDS`, with a few short retries on a transient read error.
    """

    def __init__(self, session_id):
        self.session_id = session_id
        self._timers = {}  # abs path -> threading.Timer
        self._timers_lock = threading.Lock()

    def _schedule(self, event_type, src_path):
        session = _SESSIONS.get(self.session_id)
        if session is None or session["status"] != "running":
            return
        if os.path.isdir(src_path):
            return
        if os.path.splitext(src_path)[1].lower() not in CODE_EXTENSIONS:
            return

        if event_type == "deleted":
            with self._timers_lock:
                old = self._timers.pop(src_path, None)
            if old:
                old.cancel()
            self._handle_deleted(src_path)
            return

        with self._timers_lock:
            old = self._timers.get(src_path)
            if old:
                old.cancel()
            timer = threading.Timer(_SETTLE_SECONDS, self._handle_scan, args=(event_type, src_path))
            timer.daemon = True
            self._timers[src_path] = timer
            timer.start()

    def _handle_deleted(self, src_path):
        session = _SESSIONS.get(self.session_id)
        if session is None or session["status"] != "running":
            return
        rel_path = os.path.relpath(src_path, session["path"]).replace("\\", "/")
        _push_event(self.session_id, {
            "type": "deleted", "filename": rel_path, "scan_id": None,
            "verdict": None, "risk_level": None, "vuln_probability": None,
            "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        })

    def _handle_scan(self, event_type, src_path):
        with self._timers_lock:
            self._timers.pop(src_path, None)
        session = _SESSIONS.get(self.session_id)
        if session is None or session["status"] != "running":
            return
        rel_path = os.path.relpath(src_path, session["path"]).replace("\\", "/")

        code = None
        last_err = None
        for _ in range(_READ_RETRIES):
            try:
                with open(src_path, "r", encoding="utf-8", errors="replace") as fh:
                    code = fh.read()
                break
            except OSError as e:
                last_err = e
                time.sleep(_READ_RETRY_DELAY)

        if code is None:
            _push_event(self.session_id, {
                "type": "error", "filename": rel_path, "scan_id": None,
                "verdict": None, "risk_level": None, "vuln_probability": None,
                "timestamp": dt.datetime.utcnow().isoformat() + "Z",
                "error": f"Could not read file after {_READ_RETRIES} attempts: {last_err}",
            })
            return
        if not code.strip():
            return

        db = SessionLocal()
        try:
            record = run_and_store_scan(
                db, code, session["project_name"], rel_path, "XGBoost", "watch",
                batch_id=session["batch_id"],
            )
            _push_event(self.session_id, {
                "type": event_type, "filename": rel_path, "scan_id": record.id,
                "verdict": record.verdict, "risk_level": record.risk_level,
                "vuln_probability": record.vuln_probability,
                "timestamp": dt.datetime.utcnow().isoformat() + "Z",
            })
        except Exception as e:
            _push_event(self.session_id, {
                "type": "error", "filename": rel_path, "scan_id": None,
                "verdict": None, "risk_level": None, "vuln_probability": None,
                "timestamp": dt.datetime.utcnow().isoformat() + "Z", "error": str(e),
            })
        finally:
            db.close()

    def on_created(self, event):
        if not event.is_directory:
            self._schedule("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._schedule("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._schedule("deleted", event.src_path)


def _push_event(session_id, event):
    with _LOCK:
        session = _SESSIONS.get(session_id)
        if session is None:
            return
        session["events"].append(event)
        session["seq"] += 1
        event["seq"] = session["seq"]


def start_watch(path: str, project_name: str) -> dict:
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise NotADirectoryError(f"'{path}' is not a directory the backend process can see.")

    session_id = _new_session_id()
    batch_id = session_id  # reuse the existing batch_id concept end-to-end

    # Seed scan: scan every existing matching file once, synchronously, so
    # the session starts with a populated project/score rather than an
    # empty one waiting for the first edit.
    initial_files = []
    for root, _dirs, files in os.walk(path):
        _dirs[:] = [d for d in _dirs if d.lower() not in EXCLUDED_DIR_NAMES]
        for name in files:
            if os.path.splitext(name)[1].lower() in CODE_EXTENSIONS:
                initial_files.append(os.path.join(root, name))
    initial_files = initial_files[:200]  # same cap as batch upload

    session = {
        "id": session_id, "path": path, "project_name": project_name or "Watched Project",
        "batch_id": batch_id, "status": "running", "events": collections.deque(maxlen=300),
        "seq": 0, "created_at": dt.datetime.utcnow().isoformat() + "Z",
    }
    with _LOCK:
        _SESSIONS[session_id] = session

    db = SessionLocal()
    try:
        for fpath in initial_files:
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    code = fh.read()
            except OSError:
                continue
            if not code.strip():
                continue
            rel_path = os.path.relpath(fpath, path).replace("\\", "/")
            record = run_and_store_scan(db, code, session["project_name"], rel_path, "XGBoost", "watch", batch_id=batch_id)
            _push_event(session_id, {
                "type": "initial", "filename": rel_path, "scan_id": record.id,
                "verdict": record.verdict, "risk_level": record.risk_level,
                "vuln_probability": record.vuln_probability,
                "timestamp": dt.datetime.utcnow().isoformat() + "Z",
            })
    finally:
        db.close()

    handler = _Handler(session_id)
    observer = Observer()
    observer.schedule(handler, path, recursive=True)
    observer.start()
    session["observer"] = observer

    return {"session_id": session_id, "path": path, "project_name": session["project_name"], "initial_files_scanned": len(initial_files)}


def stop_watch(session_id: str):
    with _LOCK:
        session = _SESSIONS.get(session_id)
        if session is None:
            raise KeyError("Unknown watch session")
        observer = session.get("observer")
        session["status"] = "stopped"
    if observer is not None:
        observer.stop()
        observer.join(timeout=5)


def get_events_since(session_id: str, since_seq: int = 0):
    session = _SESSIONS.get(session_id)
    if session is None:
        raise KeyError("Unknown watch session")
    events = [e for e in session["events"] if e["seq"] > since_seq]
    return session, events


def get_session(session_id: str):
    session = _SESSIONS.get(session_id)
    if session is None:
        raise KeyError("Unknown watch session")
    return session


def list_sessions():
    return list(_SESSIONS.values())


def compute_live_score(batch_id: str):
    db = SessionLocal()
    try:
        rows = db.query(ScanRecord).filter(ScanRecord.batch_id == batch_id).all()
        # Only the latest scan per filename counts toward the live score.
        latest_by_file = {}
        for r in rows:
            existing = latest_by_file.get(r.filename)
            if existing is None or r.created_at > existing.created_at:
                latest_by_file[r.filename] = r
        files = list(latest_by_file.values())
        total = len(files)
        vulnerable = sum(1 for f in files if f.verdict == "VULNERABLE")
        avg_vuln_prob = sum(f.vuln_probability or 0.0 for f in files) / total if total else 0.0
        security_score = round(max(0.0, 100.0 - avg_vuln_prob), 1)
        return {
            "total_files": total, "vulnerable_files": vulnerable, "safe_files": total - vulnerable,
            "security_score": security_score, "total_scans_recorded": len(rows),
        }
    finally:
        db.close()
