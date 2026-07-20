# =============================================================================
# routers/scan.py -- single-file, batch (multi-file / zip), and per-scan
# detail endpoints. Batch scanning covers "upload .c/.cpp/.h, entire
# folders, or zip files -> scan every file -> show progress/results".
# =============================================================================

import io
import zipfile
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, case

import ml_bridge
import recommendations
import code_intelligence
from database import get_db, ScanRecord
from schemas import CodeScanRequest, RewriteRequest, LiveScanRequest
from scan_service import run_and_store_scan, record_to_dict

router = APIRouter(prefix="/api/scan", tags=["scan"])

CODE_EXTENSIONS = (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp")
MAX_BATCH_FILES = 200
MAX_FILE_SIZE = 512_000  # 500 KB per file is generous for a single function/file

# Directories that never contain the actual shipped product -- documentation,
# example/sample snippets, and pre-built IDE integration projects. Excluded
# from every recursive ingestion path (batch zip/folder upload, GitHub clone,
# Watch Mode) so the 200-file cap on a large real repository is spent on real
# source, not tutorial code. Real, demonstrated impact during Phase 5.3
# validation: scanning curl before this exclusion spent 130 of 200 files on
# docs/examples/*.c and never reached src/ at all; scanning wolfSSL spent 194
# of 200 files on IDE/ (per-platform demo client applications) and never
# reached wolfcrypt/ or src/ (the actual cryptographic implementation).
EXCLUDED_DIR_NAMES = frozenset({"docs", "doc", "examples", "example", "sample", "samples", "ide"})


def is_scannable_path(rel_path: str) -> bool:
    """True if this repo-relative path has a real code extension and isn't
    inside a documentation/example/sample directory at any depth."""
    if not rel_path.lower().endswith(CODE_EXTENSIONS):
        return False
    parts = {p.lower() for p in rel_path.replace("\\", "/").split("/")}
    return not (parts & EXCLUDED_DIR_NAMES)


@router.post("/code")
def scan_code(req: CodeScanRequest, db: Session = Depends(get_db)):
    is_valid, msg = ml_bridge.validate_code(req.code)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)

    record = run_and_store_scan(
        db, req.code, req.project_name, req.filename, req.model_choice, req.source,
    )
    d = record_to_dict(record)
    d["validation_message"] = msg
    return d


@router.post("/live")
def scan_live(req: LiveScanRequest):
    """
    Live Monaco IDE (Phase 4, Feature 1): the SAME prediction + static
    analysis pipeline as /code and /{scan_id}/intelligence, composed into
    one call and run WITHOUT writing a ScanRecord. A debounced editor firing
    this every ~800ms would otherwise flood Scan History/Timeline/Dashboard
    with hundreds of transient draft states -- this endpoint exists purely
    to avoid that, not to add any new analysis logic. Every function called
    below is the existing, unmodified pipeline.
    """
    is_valid, msg = ml_bridge.validate_code(req.code)
    if not is_valid:
        return {"valid": False, "validation_message": msg}

    result = ml_bridge.run_prediction(req.code, req.model_choice)
    line_risks = ml_bridge.line_risk_scan(req.code)
    intel = code_intelligence.analyze(req.code, vuln_probability=result.get("vuln_probability", 0.0))
    recs = recommendations.generate_recommendations(
        result.get("ast_features", {}), result.get("metric_features", {}), line_risks,
    )
    rewrite = recommendations.suggest_secure_rewrite(req.code)

    contributions = None
    model = ml_bridge.get_xgb_model()
    if model is not None and not result.get("is_demo"):
        try:
            fv, _ = ml_bridge.full_feature_vector(req.code, result.get("ast_features", {}), result.get("metric_features", {}))
            contributions = ml_bridge.approximate_contributions(model, fv)
        except Exception:
            contributions = None

    return {
        "valid": True,
        "validation_message": msg,
        "verdict": result["verdict"],
        "vuln_probability": result["vuln_probability"],
        "safe_probability": result["safe_probability"],
        "confidence": result["confidence"],
        "risk_level": result["risk_level"],
        "risk_tag": result["risk_tag"],
        "risk_color": result["risk_color"],
        "model_used": result["model_used"],
        "is_demo": bool(result.get("is_demo")),
        "ast_features": result.get("ast_features", {}),
        "metric_features": result.get("metric_features", {}),
        "insights": result.get("insights", []),
        "line_risks": line_risks,
        "intelligence": intel,
        "recommendations": recs,
        "suggested_rewrite": rewrite,
        "contributions": contributions,
    }


@router.post("/batch")
async def scan_batch(
    project_name: str = Form("Untitled Project"),
    model_choice: str = Form("XGBoost"),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    batch_id = uuid.uuid4().hex[:12]
    to_process = []  # (filename, code_text)

    for f in files:
        raw = await f.read()
        if len(raw) > MAX_FILE_SIZE:
            continue
        name = f.filename or "unknown"
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        if not is_scannable_path(info.filename):
                            continue
                        if info.file_size > MAX_FILE_SIZE:
                            continue
                        with zf.open(info) as fh:
                            content = fh.read().decode("utf-8", errors="replace")
                        to_process.append((info.filename, content))
            except zipfile.BadZipFile:
                continue
        elif is_scannable_path(name):
            content = raw.decode("utf-8", errors="replace")
            to_process.append((name, content))

    to_process = to_process[:MAX_BATCH_FILES]
    if not to_process:
        raise HTTPException(
            status_code=400,
            detail="No scannable .c/.cpp/.h files found (directly or inside a .zip).",
        )

    results = []
    for filename, content in to_process:
        is_valid, _ = ml_bridge.validate_code(content)
        if not is_valid:
            continue
        record = run_and_store_scan(
            db, content, project_name, filename, model_choice, "batch", batch_id=batch_id,
        )
        results.append(record_to_dict(record, include_code=False))

    vulnerable = sum(1 for r in results if r["verdict"] == "VULNERABLE")
    return {
        "batch_id": batch_id,
        "total_files_submitted": len(files),
        "total_files_scanned": len(results),
        "vulnerable_count": vulnerable,
        "safe_count": len(results) - vulnerable,
        "results": results,
    }


@router.get("/batches/list")
def list_batches(db: Session = Depends(get_db)):
    rows = (
        db.query(
            ScanRecord.batch_id,
            ScanRecord.project_name,
            func.count(ScanRecord.id).label("total"),
            func.sum(case((ScanRecord.verdict == "VULNERABLE", 1), else_=0)).label("vulnerable"),
            func.max(ScanRecord.created_at).label("created_at"),
        )
        .filter(ScanRecord.batch_id.isnot(None))
        .group_by(ScanRecord.batch_id)
        .order_by(func.max(ScanRecord.created_at).desc())
        .all()
    )
    return [
        {
            "batch_id": r.batch_id,
            "project_name": r.project_name,
            "total_files": r.total,
            "vulnerable_files": int(r.vulnerable or 0),
            "created_at": r.created_at.isoformat() + "Z",
        }
        for r in rows
    ]


@router.get("/{scan_id}")
def get_scan(scan_id: str, db: Session = Depends(get_db)):
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")
    return record_to_dict(record)


@router.get("/{scan_id}/detail")
def get_scan_detail(scan_id: str, db: Session = Depends(get_db)):
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")

    code = record.code
    d = record_to_dict(record)
    ast_tree = ml_bridge.get_ast_tree(code)
    line_risks = ml_bridge.line_risk_scan(code)
    insights = ml_bridge.describe_features(d["ast_features"], d["metric_features"])
    recs = recommendations.generate_recommendations(
        d["ast_features"],
        d["metric_features"],
        line_risks,
    )
    rewrite = recommendations.suggest_secure_rewrite(code)

    contributions = None
    model = ml_bridge.get_xgb_model()
    if model is not None and not record.is_demo:
        try:
            fv, _ = ml_bridge.full_feature_vector(code, d["ast_features"], d["metric_features"])
            contributions = ml_bridge.approximate_contributions(model, fv)
        except Exception:
            contributions = None

    return {
        "id": record.id,
        "insights": insights,
        "ast_tree": ast_tree,
        "line_risks": line_risks,
        "recommendations": recs,
        "suggested_rewrite": rewrite,
        "contributions": contributions,
        "pca_background": ml_bridge.pca_background(),
    }


@router.post("/rewrite")
def rewrite_code(req: RewriteRequest):
    return recommendations.suggest_secure_rewrite(req.code)


@router.delete("/{scan_id}")
def delete_scan(scan_id: str, db: Session = Depends(get_db)):
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")
    db.delete(record)
    db.commit()
    return {"deleted": scan_id}
