# =============================================================================
# routers/scan.py -- single-file, batch (multi-file / zip), and per-scan
# detail endpoints. Batch scanning covers "upload .c/.cpp/.h, entire
# folders, or zip files -> scan every file -> show progress/results".
# =============================================================================

import io
import os
import re
import zipfile
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, case

import job_service
import ml_bridge
import recommendations
import code_intelligence
from database import get_db, ScanRecord, SessionLocal
from schemas import CodeScanRequest, RewriteRequest, LiveScanRequest
from scan_service import run_and_store_scan, record_to_dict

router = APIRouter(prefix="/api/scan", tags=["scan"])

CODE_EXTENSIONS = (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp")
MAX_BATCH_FILES = 200
MAX_FILE_SIZE = 512_000  # 500 KB per file is generous for a single function/file

# Zip-bomb defense: a small, highly-compressed archive can expand to an
# enormous number of entries or an enormous total uncompressed size. Both are
# checked from zf.infolist() metadata BEFORE any member is decompressed/read,
# so a malicious archive is rejected cheaply rather than after doing the
# expensive work it was designed to trigger.
MAX_ZIP_MEMBERS = 5_000
MAX_ZIP_TOTAL_UNCOMPRESSED = 200_000_000  # 200 MB combined, generous for real source repos

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


_DRIVE_LETTER_RE = re.compile(r"^[A-Za-z]:")


def is_safe_archive_member_path(member_path: str) -> bool:
    """
    Defensive Zip Slip / path-traversal guard for ZIP archive member names.

    This project never extracts ZIP entries to disk -- every member is read
    into memory and stored as a database column (see scan_batch below), so a
    malicious `../../etc/passwd`-style member name cannot actually escape any
    directory today. This guard exists anyway as defense-in-depth: if the
    ingestion path is ever changed to write to disk, this check must already
    be in place rather than added later under pressure. Rejects:
      - absolute POSIX paths ("/etc/passwd")
      - absolute Windows paths ("C:\\Windows\\...")
      - any path with a ".." traversal segment, at any depth
    """
    normalized = member_path.replace("\\", "/")
    if normalized.startswith("/"):
        return False
    if _DRIVE_LETTER_RE.match(normalized):
        return False
    parts = normalized.split("/")
    if ".." in parts:
        return False
    if os.path.isabs(normalized):
        return False
    return True


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


def _run_batch_job(
    batch_id: str,
    to_process: list,
    project_name: str,
    model_choice: str,
    total_files_submitted: int,
    files_detected: int,
    skip_reasons_so_far: list,
) -> None:
    """
    Runs off the request thread (FastAPI BackgroundTasks -> AnyIO
    threadpool, the same offloading plain `def` routes already get -- see
    docs/ASYNC_SCAN_DESIGN.md Sec 2/5). Opens its own DB session rather
    than reusing the request's, matching github_service.py's existing
    background-work pattern (SessionLocal() created fresh, not borrowed
    from a request-scoped Depends(get_db)).
    """
    db = SessionLocal()
    try:
        job_service.mark_running(db, batch_id)

        results = []
        skip_invalid_content = 0
        for filename, content in to_process:
            is_valid, _ = ml_bridge.validate_code(content)
            if not is_valid:
                skip_invalid_content += 1
                job_service.increment_progress(db, batch_id, failed_delta=1)
                continue
            record = run_and_store_scan(
                db, content, project_name, filename, model_choice, "batch", batch_id=batch_id,
            )
            results.append(record_to_dict(record, include_code=False))
            job_service.increment_progress(db, batch_id, completed_delta=1)

        skip_reasons = list(skip_reasons_so_far)
        if skip_invalid_content > 0:
            skip_reasons.append(f"{skip_invalid_content} file(s) failed content validation (empty/malformed)")

        vulnerable = sum(1 for r in results if r["verdict"] == "VULNERABLE")
        result = {
            "batch_id": batch_id,
            "total_files_submitted": total_files_submitted,
            "files_detected": files_detected,
            "total_files_scanned": len(results),
            "files_skipped": files_detected - len(results),
            "skip_reasons": skip_reasons,
            "vulnerable_count": vulnerable,
            "safe_count": len(results) - vulnerable,
            "results": results,
        }
        job_service.mark_succeeded(db, batch_id, result)
    except Exception as e:
        job_service.mark_failed(db, batch_id, str(e))
    finally:
        db.close()


@router.post("/batch")
def scan_batch(
    background_tasks: BackgroundTasks,
    project_name: str = Form("Untitled Project"),
    model_choice: str = Form("XGBoost"),
    files: list[UploadFile] = File(...),
):
    """
    Submits an async job and returns immediately (docs/ASYNC_SCAN_DESIGN.md)
    instead of blocking for the full scan duration. Upload read + ZIP
    decompress + filename/path/size filtering still happen synchronously
    here -- fast, and files_total needs to be known before responding --
    only the per-file inference loop (the actual multi-minute cost) moves
    into _run_batch_job above, off the event loop.

    Plain `def`, not `async def`: this is itself part of the fix. The
    previous `async def` version's inference loop had no `await` in it,
    so it ran directly on the event loop thread instead of being
    threadpooled, freezing the entire server for every user for the full
    scan duration -- confirmed in docs/ASYNC_SCAN_DESIGN.md Sec 2. Plain
    `def` here means Starlette threadpools this handler exactly like
    every other route already is, and reading via `f.file.read()`
    (sync) instead of `await f.read()` (async) is required for that.
    """
    batch_id = uuid.uuid4().hex[:12]
    detected = []  # (filename, code_text) -- every file that passed extension/dir/size/path filtering, before the batch cap

    # Real skip-reason counters -- surfaced in the response so the UI can
    # honestly report "scanned X of Y detected files" instead of silently
    # dropping files with no explanation (see docs/FINAL_PRODUCT_AUDIT.md).
    skip_oversized = 0
    skip_unsupported = 0
    skip_unsafe_path = 0
    skip_corrupt_zip = 0
    skip_zip_bomb = 0

    for f in files:
        raw = f.file.read()
        name = f.filename or "unknown"
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    infolist = zf.infolist()
                    if len(infolist) > MAX_ZIP_MEMBERS or sum(i.file_size for i in infolist) > MAX_ZIP_TOTAL_UNCOMPRESSED:
                        skip_zip_bomb += 1
                        continue
                    for info in infolist:
                        if info.is_dir():
                            continue
                        if not is_safe_archive_member_path(info.filename):
                            skip_unsafe_path += 1
                            continue
                        if not is_scannable_path(info.filename):
                            skip_unsupported += 1
                            continue
                        if info.file_size > MAX_FILE_SIZE:
                            skip_oversized += 1
                            continue
                        with zf.open(info) as fh:
                            content = fh.read().decode("utf-8", errors="replace")
                        detected.append((info.filename, content))
            except zipfile.BadZipFile:
                skip_corrupt_zip += 1
                continue
        elif len(raw) > MAX_FILE_SIZE:
            skip_oversized += 1
        elif is_scannable_path(name):
            content = raw.decode("utf-8", errors="replace")
            detected.append((name, content))
        else:
            skip_unsupported += 1

    files_detected = len(detected)
    to_process = detected[:MAX_BATCH_FILES]
    skip_capped = files_detected - len(to_process)

    if not to_process:
        raise HTTPException(
            status_code=400,
            detail="No scannable .c/.cpp/.h files found (directly or inside a .zip).",
        )

    # Skip reasons knowable synchronously, before any inference runs --
    # skip_invalid_content (only discoverable per-file, during scanning)
    # is appended inside _run_batch_job and folded into the final result.
    skip_reasons_so_far = []
    if skip_capped > 0:
        skip_reasons_so_far.append(f"{skip_capped} file(s) beyond the {MAX_BATCH_FILES}-file-per-scan cap")
    if skip_oversized > 0:
        skip_reasons_so_far.append(f"{skip_oversized} file(s) exceeded the {MAX_FILE_SIZE // 1000}KB size limit")
    if skip_unsupported > 0:
        skip_reasons_so_far.append(f"{skip_unsupported} file(s) unsupported extension or excluded directory")
    if skip_unsafe_path > 0:
        skip_reasons_so_far.append(f"{skip_unsafe_path} archive member(s) rejected for an unsafe path (../ or absolute)")
    if skip_corrupt_zip > 0:
        skip_reasons_so_far.append(f"{skip_corrupt_zip} corrupt/unreadable ZIP archive(s)")
    if skip_zip_bomb > 0:
        skip_reasons_so_far.append(f"{skip_zip_bomb} ZIP archive(s) rejected (too many entries or too large uncompressed)")

    db = SessionLocal()
    try:
        job_service.create_job(db, batch_id, kind="batch", files_total=len(to_process))
    finally:
        db.close()

    background_tasks.add_task(
        _run_batch_job, batch_id, to_process, project_name, model_choice,
        len(files), files_detected, skip_reasons_so_far,
    )

    return {
        "batch_id": batch_id,
        "status": "queued",
        "files_total": len(to_process),
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


@router.get("/jobs/{batch_id}")
def get_job(batch_id: str, db: Session = Depends(get_db)):
    """
    Polled by the frontend (docs/ASYNC_SCAN_DESIGN.md Sec 6/7) after
    POST /batch returns a batch_id. Declared before /{scan_id} below even
    though the two route shapes don't actually collide ("/jobs/xyz" is two
    path segments, "/{scan_id}" matches exactly one) -- more-specific-first
    is just the clearer convention to read, not a correctness requirement
    here.
    """
    job = job_service.get_job(db, batch_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_service.job_to_dict(job)


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
