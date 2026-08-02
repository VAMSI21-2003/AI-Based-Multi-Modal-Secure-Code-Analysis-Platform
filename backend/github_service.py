# =============================================================================
# github_service.py -- Phase 6: GitHub Mode.
#
# Clones a public GitHub (or any plain git) repository to a temporary local
# directory, scans every matching source file through the EXISTING pipeline
# (scan_service.run_and_store_scan, unchanged), records the commit history
# via `git log`, then deletes the temporary clone -- only the resulting
# ScanRecord rows (tagged with a batch_id) persist, exactly like any other
# batch scan. This means Project Scanner, Dependency Graph, and the Batch
# PDF export all work on a GitHub-cloned repo for free, with zero new code
# in any of those pages.
#
# Security note: the repo URL is validated to be a plain http(s) URL (no
# `-`-prefixed strings, no ssh/local paths) and passed to `git` as a real
# argv list (never through a shell), so there is no command-injection
# surface. Nothing in the cloned repo is ever executed -- it is only parsed
# (tree-sitter) and read as text (CodeBERT tokenizer), the same as any
# uploaded file.
# =============================================================================

import ipaddress
import os
import re
import shutil
import socket
import subprocess
import tempfile
import uuid
from urllib.parse import urlparse

import datetime as dt

import job_service
from database import SessionLocal, GitHubBatchMeta
from scan_service import run_and_store_scan
from routers.scan import CODE_EXTENSIONS, EXCLUDED_DIR_NAMES

MAX_REPO_FILES = 200
MAX_FILE_SIZE = 512_000
CLONE_TIMEOUT_SEC = 90
CLONE_DEPTH = 50

_URL_RE = re.compile(r"^https?://[A-Za-z0-9._~%\-]+(/[A-Za-z0-9._~%\-./]*)?$")

_COMMIT_HISTORY = {}  # batch_id -> list of commit dicts (in-memory, mirrors watch_service's session store)


def _is_unsafe_address(ip_str: str) -> bool:
    """
    True if this IP literal is loopback, private (RFC1918), link-local
    (includes the 169.254.169.254 cloud-metadata address on AWS/GCP/Azure),
    reserved, multicast, or unspecified -- i.e. anywhere this backend's own
    "clone a public repository" feature should never be allowed to reach.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable -- fail closed, not open
    return (
        ip.is_loopback or ip.is_private or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def _validate_url(url: str) -> str:
    """
    Validates URL syntax AND that the hostname does not resolve to an
    internal/private/loopback/link-local address -- SSRF hardening for the
    "clone an arbitrary user-supplied URL" feature. This checks DNS
    resolution at validation time; it does not (and practically cannot,
    with a plain `git clone` subprocess) re-verify the IP `git` itself
    connects to a few moments later, so a DNS-rebinding attack (the hostname
    resolves safely here, then re-resolves to an internal IP by the time
    `git` connects) is a known, accepted residual risk -- closing it fully
    would require intercepting git's own connection (e.g. a pinned
    resolver/proxy), which is out of scope for this research/demo-scale
    scanner. Documented, not silently ignored.
    """
    url = (url or "").strip()
    if not _URL_RE.match(url):
        raise ValueError("Only plain http(s) git URLs are supported (e.g. https://github.com/owner/repo.git)")

    hostname = urlparse(url).hostname
    if not hostname:
        raise ValueError("Could not parse a hostname from this URL.")
    if hostname.lower() in ("localhost", "metadata.google.internal"):
        raise ValueError("Refusing to clone from a local/internal hostname.")

    # Literal IP in the URL itself (e.g. https://127.0.0.1/x.git)?
    try:
        literal_ip = ipaddress.ip_address(hostname)
        if _is_unsafe_address(str(literal_ip)):
            raise ValueError("Refusing to clone from a private/internal/loopback IP address.")
    except ValueError as e:
        if "Refusing" in str(e):
            raise
        # Not a literal IP -- fall through to DNS resolution below.

    # Resolve the hostname and check EVERY returned address, not just the
    # first -- a hostname can have multiple A/AAAA records.
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"Could not resolve hostname: {hostname}")
    for family, _, _, _, sockaddr in addr_infos:
        resolved_ip = sockaddr[0]
        if _is_unsafe_address(resolved_ip):
            raise ValueError(
                f"Refusing to clone '{hostname}': it resolves to a private/internal/loopback address ({resolved_ip})."
            )

    return url


def _run_git(args, cwd=None, timeout=CLONE_TIMEOUT_SEC):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False,
    )


def _get_commit_history(repo_dir: str, limit: int = 20) -> list:
    sep = "\x1f"
    fmt = sep.join(["%H", "%an", "%ad", "%s"])
    result = _run_git(["log", f"-{limit}", f"--pretty=format:{fmt}", "--date=iso-strict"], cwd=repo_dir, timeout=20)
    if result.returncode != 0:
        return []
    commits = []
    for line in result.stdout.splitlines():
        parts = line.split(sep)
        if len(parts) != 4:
            continue
        commits.append({"hash": parts[0][:10], "author": parts[1], "date": parts[2], "message": parts[3]})
    return commits


def _get_head_branch(repo_dir: str) -> str | None:
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir, timeout=15)
    branch = result.stdout.strip()
    return branch if result.returncode == 0 and branch and branch != "HEAD" else None


def _get_head_commit_sha(repo_dir: str) -> str | None:
    result = _run_git(["rev-parse", "HEAD"], cwd=repo_dir, timeout=15)
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else None


def submit_scan_job(repo_url: str, project_name: str, background_tasks) -> str:
    """
    Entry point for POST /api/github/scan (docs/ASYNC_SCAN_DESIGN.md).
    Validates the URL synchronously -- fail fast on a bad URL rather than
    queuing a job doomed to fail minutes later, per the design's explicit
    call -- then creates a scan_jobs row and schedules the actual
    clone+scan as a background task. Returns the new batch_id immediately;
    raises ValueError (unchanged from before) on a bad/unsafe URL, which
    the router still maps to a synchronous 400.
    """
    url = _validate_url(repo_url)
    batch_id = "gh_" + uuid.uuid4().hex[:10]

    db = SessionLocal()
    try:
        # files_total isn't known yet -- cloning + walking the repo hasn't
        # happened. Set to 0 here; _run_github_scan_job calls
        # job_service.set_files_total() once the real count is known,
        # same two-step pattern batch jobs don't need (their files_total
        # IS known synchronously, before the job row is even created).
        job_service.create_job(db, batch_id, kind="github", files_total=0)
    finally:
        db.close()

    background_tasks.add_task(_run_github_scan_job, batch_id, url, project_name)
    return batch_id


def _run_github_scan_job(batch_id: str, url: str, project_name: str = None) -> None:
    """
    The clone + scan + finalize work previously done inline inside
    scan_repo() (now removed), run off the request thread via
    BackgroundTasks. Any exception here -- clone failure, no scannable
    files, or anything unexpected -- is caught and recorded as a "failed"
    job rather than propagated, since there is no HTTP response left to
    attach an error status code to once the request has already returned
    "queued".
    """
    db = SessionLocal()
    try:
        job_service.mark_running(db, batch_id)

        repo_name = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        project_name = project_name or repo_name

        tmp_dir = tempfile.mkdtemp(prefix="secure_code_ai_ghmode_")
        try:
            clone_result = _run_git(
                ["clone", "--depth", str(CLONE_DEPTH), "--single-branch", url, tmp_dir],
                timeout=CLONE_TIMEOUT_SEC,
            )
            if clone_result.returncode != 0:
                raise RuntimeError(f"git clone failed: {clone_result.stderr.strip()[:400]}")

            commits = _get_commit_history(tmp_dir, limit=20)
            branch = _get_head_branch(tmp_dir)
            commit_sha = _get_head_commit_sha(tmp_dir)

            # "Detected" = every file this platform's own extension/directory
            # filtering considers in-scope, BEFORE the per-scan file cap --
            # reported honestly so a capped scan never gets silently presented
            # as full repository coverage.
            detected_files = []
            for root, dirs, files in os.walk(tmp_dir):
                dirs[:] = [d for d in dirs if d != ".git" and d.lower() not in EXCLUDED_DIR_NAMES]
                for name in files:
                    if os.path.splitext(name)[1].lower() not in CODE_EXTENSIONS:
                        continue
                    full = os.path.join(root, name)
                    try:
                        if os.path.getsize(full) > MAX_FILE_SIZE:
                            continue
                    except OSError:
                        continue
                    detected_files.append(full)

            matched_files = detected_files[:MAX_REPO_FILES]

            if not matched_files:
                raise RuntimeError("No scannable .c/.cpp/.h files found in this repository.")

            job_service.set_files_total(db, batch_id, len(matched_files))

            scanned = 0
            unreadable = 0
            for full in matched_files:
                try:
                    with open(full, "r", encoding="utf-8", errors="replace") as fh:
                        code = fh.read()
                except OSError:
                    unreadable += 1
                    job_service.increment_progress(db, batch_id, failed_delta=1)
                    continue
                if not code.strip():
                    unreadable += 1
                    job_service.increment_progress(db, batch_id, failed_delta=1)
                    continue
                rel_path = os.path.relpath(full, tmp_dir).replace("\\", "/")
                run_and_store_scan(db, code, project_name, rel_path, "XGBoost", "github", batch_id=batch_id)
                scanned += 1
                job_service.increment_progress(db, batch_id, completed_delta=1)

            capped_out = len(detected_files) - len(matched_files)
            skip_reasons = []
            if capped_out > 0:
                skip_reasons.append(f"{capped_out} file(s) beyond this platform's {MAX_REPO_FILES}-file-per-scan cap")
            if unreadable > 0:
                skip_reasons.append(f"{unreadable} file(s) empty or unreadable")

            db.add(GitHubBatchMeta(
                batch_id=batch_id, repo_url=url, repo_name=repo_name, branch=branch, commit_sha=commit_sha,
                files_detected=len(detected_files), files_analyzed=scanned,
                files_skipped=len(detected_files) - scanned, skip_reasons="; ".join(skip_reasons),
                scanned_at=dt.datetime.utcnow(),
            ))
            db.commit()

            _COMMIT_HISTORY[batch_id] = commits

            result = {
                "batch_id": batch_id, "repo_url": url, "repo_name": repo_name, "project_name": project_name,
                "branch": branch, "commit_sha": commit_sha,
                "files_scanned": scanned, "files_found": len(matched_files),
                "files_detected": len(detected_files), "files_skipped": len(detected_files) - scanned,
                "skip_reasons": skip_reasons, "commits_recorded": len(commits),
            }
            job_service.mark_succeeded(db, batch_id, result)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as e:
        job_service.mark_failed(db, batch_id, str(e))
    finally:
        db.close()


def get_commit_history(batch_id: str) -> list:
    return _COMMIT_HISTORY.get(batch_id, [])


def get_batch_meta(batch_id: str) -> dict | None:
    """Reads persisted repo provenance for a batch_id -- unlike commit history
    (in-memory only), this survives a backend restart."""
    db = SessionLocal()
    try:
        row = db.get(GitHubBatchMeta, batch_id)
        if not row:
            return None
        return {
            "batch_id": row.batch_id, "repo_url": row.repo_url, "repo_name": row.repo_name,
            "branch": row.branch, "commit_sha": row.commit_sha,
            "files_detected": row.files_detected, "files_analyzed": row.files_analyzed,
            "files_skipped": row.files_skipped,
            "skip_reasons": [r for r in (row.skip_reasons or "").split("; ") if r],
            "scanned_at": row.scanned_at.isoformat() + "Z" if row.scanned_at else None,
        }
    finally:
        db.close()
