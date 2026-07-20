# =============================================================================
# routers/export.py -- Export Center endpoints (Executive PDF, Developer
# PDF, HTML report, Research Appendix PDF). Purely additive.
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, HTMLResponse
from sqlalchemy.orm import Session

import ml_bridge
import code_intelligence
import recommendations
import export_center
from database import get_db, ScanRecord
from scan_service import record_to_dict
from routers.research import model_architecture
from routers.research import _eval_curves
from routers.project import project_summary

router = APIRouter(prefix="/api/export", tags=["export"])


def _load_scan(scan_id, db):
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")
    return record


@router.get("/pdf/executive/{scan_id}")
def executive_pdf(scan_id: str, db: Session = Depends(get_db)):
    record = _load_scan(scan_id, db)
    scan = record_to_dict(record, include_code=False)
    pdf = export_center.build_executive_pdf(scan)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=executive_report_{scan_id}.pdf"})


@router.get("/pdf/developer/{scan_id}")
def developer_pdf(scan_id: str, db: Session = Depends(get_db)):
    record = _load_scan(scan_id, db)
    scan = record_to_dict(record)
    line_risks = ml_bridge.line_risk_scan(record.code)
    recs = recommendations.generate_recommendations(scan["ast_features"], scan["metric_features"], line_risks)
    intel = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
    pdf = export_center.build_developer_pdf(scan, line_risks, recs, intel)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=developer_report_{scan_id}.pdf"})


@router.get("/html/{scan_id}")
def html_report(scan_id: str, db: Session = Depends(get_db)):
    record = _load_scan(scan_id, db)
    scan = record_to_dict(record)
    line_risks = ml_bridge.line_risk_scan(record.code)
    recs = recommendations.generate_recommendations(scan["ast_features"], scan["metric_features"], line_risks)
    html = export_center.build_html_report(scan, line_risks, recs)
    return HTMLResponse(html, headers={"Content-Disposition": f"attachment; filename=report_{scan_id}.html"})


@router.get("/pdf/research")
def research_pdf():
    arch = model_architecture()
    curves = _eval_curves() or {}
    pdf = export_center.build_research_pdf(arch, curves)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=research_appendix.pdf"})


@router.get("/docx/{scan_id}")
def word_report(scan_id: str, db: Session = Depends(get_db)):
    record = _load_scan(scan_id, db)
    scan = record_to_dict(record)
    line_risks = ml_bridge.line_risk_scan(record.code)
    recs = recommendations.generate_recommendations(scan["ast_features"], scan["metric_features"], line_risks)
    intel = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
    docx_bytes = export_center.build_word_report(scan, line_risks, recs, intel)
    return Response(
        docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=developer_report_{scan_id}.docx"},
    )


@router.get("/pptx/{scan_id}")
def pptx_report(scan_id: str, db: Session = Depends(get_db)):
    record = _load_scan(scan_id, db)
    scan = record_to_dict(record)
    line_risks = ml_bridge.line_risk_scan(record.code)
    recs = recommendations.generate_recommendations(scan["ast_features"], scan["metric_features"], line_risks)
    intel = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
    pptx_bytes = export_center.build_pptx_report(scan, line_risks, recs, intel)
    return Response(
        pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename=security_deck_{scan_id}.pptx"},
    )


@router.get("/pdf/enterprise/{scan_id}")
def enterprise_pdf(scan_id: str, db: Session = Depends(get_db)):
    record = _load_scan(scan_id, db)
    scan = record_to_dict(record)
    line_risks = ml_bridge.line_risk_scan(record.code)
    recs = recommendations.generate_recommendations(scan["ast_features"], scan["metric_features"], line_risks)
    intel = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
    arch = model_architecture()
    curves = _eval_curves() or {}
    pdf = export_center.build_enterprise_pdf(scan, line_risks, recs, intel, arch, curves)
    return Response(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=enterprise_report_{scan_id}.pdf"},
    )


@router.get("/pdf/enterprise-project/{batch_id}")
def enterprise_project_pdf(batch_id: str, db: Session = Depends(get_db)):
    project = project_summary(batch_id, db)
    pdf = export_center.build_enterprise_project_pdf(project)
    return Response(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=repository_report_{batch_id}.pdf"},
    )
