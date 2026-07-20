# =============================================================================
# routers/watch.py -- Real-Time Watch Mode endpoints (Phase 4).
# Purely additive: starts/stops a watchdog-based folder watcher and exposes
# its live event feed + live project score via short-poll REST endpoints.
# Rescans go through the existing scan pipeline (scan_service) unchanged.
# =============================================================================

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends

import watch_service
from database import get_db, ScanRecord

router = APIRouter(prefix="/api/watch", tags=["watch"])


class StartWatchRequest(BaseModel):
    path: str
    project_name: str = "Watched Project"


@router.post("/start")
def start(req: StartWatchRequest):
    try:
        result = watch_service.start_watch(req.path, req.project_name)
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/{session_id}/stop")
def stop(session_id: str):
    try:
        watch_service.stop_watch(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown watch session")
    return {"session_id": session_id, "status": "stopped"}


@router.get("/sessions")
def sessions():
    out = []
    for s in watch_service.list_sessions():
        score = watch_service.compute_live_score(s["batch_id"])
        out.append({
            "session_id": s["id"], "path": s["path"], "project_name": s["project_name"],
            "status": s["status"], "created_at": s["created_at"], "batch_id": s["batch_id"],
            "score": score,
        })
    return out


@router.get("/{session_id}/events")
def events(session_id: str, since: int = Query(0)):
    try:
        session, new_events = watch_service.get_events_since(session_id, since)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown watch session")
    score = watch_service.compute_live_score(session["batch_id"])
    next_since = session["seq"]
    return {
        "session_id": session_id, "status": session["status"], "path": session["path"],
        "project_name": session["project_name"], "batch_id": session["batch_id"],
        "events": new_events, "next_since": next_since, "score": score,
    }


@router.get("/{session_id}/diff/{filename:path}")
def diff(session_id: str, filename: str, db: Session = Depends(get_db)):
    try:
        session = watch_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown watch session")

    rows = (
        db.query(ScanRecord)
        .filter(ScanRecord.batch_id == session["batch_id"], ScanRecord.filename == filename)
        .order_by(ScanRecord.created_at.desc())
        .limit(2)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No scans recorded yet for this file in this session")

    current = rows[0]
    previous = rows[1] if len(rows) > 1 else None
    return {
        "filename": filename,
        "current": {"scan_id": current.id, "code": current.code, "verdict": current.verdict, "risk_level": current.risk_level, "created_at": current.created_at.isoformat() + "Z"},
        "previous": (
            {"scan_id": previous.id, "code": previous.code, "verdict": previous.verdict, "risk_level": previous.risk_level, "created_at": previous.created_at.isoformat() + "Z"}
            if previous else None
        ),
    }
