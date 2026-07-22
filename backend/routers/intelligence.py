# =============================================================================
# routers/intelligence.py -- "AI Code Explanation" endpoint.
# Computed fresh from the scan's stored source on every request, so it is
# always in sync with the latest scan (no caching / staleness).
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import analysis_cache
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


@router.get("/{scan_id}/optimization")
def get_optimization(scan_id: str, db: Session = Depends(get_db)):
    """
    Deterministic performance/efficiency heuristics -- see
    optimization_analyzer.py and docs/OPTIMIZATION_SUGGESTIONS_DESIGN.md.
    Explicitly separate from /intelligence and /detail: never merged into
    vuln_probability/risk_level, always labeled "heuristic_based": true.
    Lazily computed and cached per ScanRecord.id (analysis_cache), same
    pattern as get_intel()/get_line_risks().
    """
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")
    return analysis_cache.get_optimization_findings(record)
