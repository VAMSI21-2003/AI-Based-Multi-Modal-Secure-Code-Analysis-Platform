# =============================================================================
# routers/system.py -- System Monitor: CPU/RAM, model load time, prediction
# latency, files scanned, average scan time. Pure telemetry -- read-only,
# no writes to the scan database.
# =============================================================================

import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

import system_monitor
from database import get_db, ScanRecord

router = APIRouter(prefix="/api/system", tags=["system"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fixed, known, repo-relative paths only -- never user input -- so this is
# safe read-only access to the platform's own infra files, for the Platform
# hub's Docker / CI-CD tabs (Phase 5). Shows the REAL file contents rather
# than a description of them.
PLATFORM_FILES = {
    "docker_compose": "docker-compose.yml",
    "backend_dockerfile": "backend/Dockerfile",
    "frontend_dockerfile": "frontend/Dockerfile",
    "nginx_conf": "frontend/nginx.conf",
    "github_workflow": ".github/workflows/security_scan.yml",
    "ci_scan_script": "backend/ci_scan.py",
}


@router.get("/stats")
def system_stats(db: Session = Depends(get_db)):
    total_scans = db.query(func.count(ScanRecord.id)).scalar() or 0
    return system_monitor.get_stats(files_scanned=total_scans)


@router.get("/platform-files")
def platform_files():
    out = {}
    for key, rel_path in PLATFORM_FILES.items():
        full = os.path.join(PROJECT_ROOT, rel_path)
        if os.path.exists(full):
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                out[key] = {"path": rel_path, "exists": True, "content": fh.read()}
        else:
            out[key] = {"path": rel_path, "exists": False, "content": None}
    return out
