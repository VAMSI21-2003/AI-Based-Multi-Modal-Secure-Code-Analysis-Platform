# =============================================================================
# routers/github.py -- GitHub Mode endpoints (Phase 6).
# Purely additive: clones + scans a repo through github_service, then reuses
# the existing scan.py/project.py/report.py endpoints for everything else
# (the clone's ScanRecord rows are a normal batch, tagged with a "gh_" batch_id).
# =============================================================================

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

import github_service

router = APIRouter(prefix="/api/github", tags=["github"])


class GitHubScanRequest(BaseModel):
    repo_url: str
    project_name: str | None = None


@router.post("/scan")
def scan(req: GitHubScanRequest, background_tasks: BackgroundTasks):
    """
    Submits an async job and returns immediately (docs/ASYNC_SCAN_DESIGN.md)
    instead of blocking for the full clone+scan duration. URL validation
    (github_service._validate_url) still happens synchronously here -- a
    bad/unsafe URL still gets an immediate 400, never a job that's queued
    only to fail. Clone failures and "no scannable files" (previously
    RuntimeError -> 422) now surface as the job's status="failed" + error
    field instead, since there's no HTTP response left to attach a status
    code to once "queued" has already been returned -- poll
    GET /api/scan/jobs/{batch_id} for the outcome.
    """
    try:
        batch_id = github_service.submit_scan_job(req.repo_url, req.project_name, background_tasks)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"batch_id": batch_id, "status": "queued"}


@router.get("/{batch_id}/commits")
def commits(batch_id: str):
    return {"batch_id": batch_id, "commits": github_service.get_commit_history(batch_id)}


@router.get("/{batch_id}/meta")
def meta(batch_id: str):
    result = github_service.get_batch_meta(batch_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No repository metadata recorded for this batch_id.")
    return result
