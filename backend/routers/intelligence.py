# =============================================================================
# routers/intelligence.py -- "AI Code Explanation" endpoint.
# Computed fresh from the scan's stored source on every request, so it is
# always in sync with the latest scan (no caching / staleness).
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import code_intelligence
from database import get_db, ScanRecord

router = APIRouter(prefix="/api/scan", tags=["intelligence"])


@router.get("/{scan_id}/intelligence")
def get_intelligence(scan_id: str, function: str = Query(None), db: Session = Depends(get_db)):
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")

    result = code_intelligence.analyze(
        record.code,
        vuln_probability=record.vuln_probability or 0.0,
        cfg_function=function,
    )
    return result
