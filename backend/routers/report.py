# =============================================================================
# routers/report.py -- Security Report (PDF) endpoints.
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

import ml_bridge
import recommendations
import report as report_builder
from database import get_db, ScanRecord
from scan_service import record_to_dict

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("/pdf/{scan_id}")
def scan_pdf(scan_id: str, db: Session = Depends(get_db)):
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")

    scan = record_to_dict(record)
    line_risks = ml_bridge.line_risk_scan(record.code)
    recs = recommendations.generate_recommendations(scan["ast_features"], scan["metric_features"], line_risks)

    pdf_bytes = report_builder.build_single_scan_pdf(scan, line_risks, recs)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=scan_report_{scan_id}.pdf"},
    )


@router.get("/pdf/batch/{batch_id}")
def batch_pdf(batch_id: str, db: Session = Depends(get_db)):
    records = db.query(ScanRecord).filter(ScanRecord.batch_id == batch_id).all()
    if not records:
        raise HTTPException(status_code=404, detail="Batch not found")

    results = [record_to_dict(r, include_code=False) for r in records]
    vulnerable = sum(1 for r in results if r["verdict"] == "VULNERABLE")
    batch_summary = {
        "total_files_scanned": len(results),
        "vulnerable_count": vulnerable,
        "safe_count": len(results) - vulnerable,
    }
    project_name = records[0].project_name

    pdf_bytes = report_builder.build_batch_pdf(batch_summary, results, project_name)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=project_report_{batch_id}.pdf"},
    )
