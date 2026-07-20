# =============================================================================
# routers/github.py -- GitHub Mode endpoints (Phase 6).
# Purely additive: clones + scans a repo through github_service, then reuses
# the existing scan.py/project.py/report.py endpoints for everything else
# (the clone's ScanRecord rows are a normal batch, tagged with a "gh_" batch_id).
# =============================================================================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import github_service

router = APIRouter(prefix="/api/github", tags=["github"])


class GitHubScanRequest(BaseModel):
    repo_url: str
    project_name: str | None = None


@router.post("/scan")
def scan(req: GitHubScanRequest):
    try:
        result = github_service.scan_repo(req.repo_url, req.project_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error cloning/scanning repository: {e}")
    return result


@router.get("/{batch_id}/commits")
def commits(batch_id: str):
    return {"batch_id": batch_id, "commits": github_service.get_commit_history(batch_id)}
