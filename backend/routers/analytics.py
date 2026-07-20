# =============================================================================
# routers/analytics.py -- Project Analytics module: distributions, trends,
# model performance (read from the EXISTING training_metadata.json -- not
# recomputed), and dataset statistics (read from the EXISTING processed
# dataset files -- not reprocessed).
# =============================================================================

import os
import json
import functools
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

import ml_bridge
from database import get_db, ScanRecord

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRAINING_METADATA_PATH = os.path.join(PROJECT_ROOT, "models", "training_metadata.json")
DEVIGN_CLEANED_PATH = os.path.join(PROJECT_ROOT, "dataset", "processed", "devign_cleaned.csv")


@router.get("/overview")
def analytics_overview(db: Session = Depends(get_db)):
    total = db.query(func.count(ScanRecord.id)).scalar() or 0

    risk_dist = dict(
        db.query(ScanRecord.risk_level, func.count(ScanRecord.id)).group_by(ScanRecord.risk_level).all()
    )
    verdict_dist = dict(
        db.query(ScanRecord.verdict, func.count(ScanRecord.id)).group_by(ScanRecord.verdict).all()
    )
    source_dist = dict(
        db.query(ScanRecord.source, func.count(ScanRecord.id)).group_by(ScanRecord.source).all()
    )
    project_dist = dict(
        db.query(ScanRecord.project_name, func.count(ScanRecord.id)).group_by(ScanRecord.project_name).all()
    )

    # Capped at 100 (was 500, and previously unordered so an arbitrary 500
    # rather than a meaningful subset) -- same ~11ms/record regex-scan cost
    # as dashboard_stats() above, so 500 records cost ~5s on every load once
    # the DB has a few hundred scans. Ordered + capped at 100 recent
    # vulnerable records for a representative, deterministic sample.
    codes = (
        db.query(ScanRecord.code)
        .filter(ScanRecord.verdict == "VULNERABLE")
        .order_by(ScanRecord.created_at.desc())
        .limit(100)
        .all()
    )
    cwe_counter = Counter()
    for (code,) in codes:
        for lr in ml_bridge.line_risk_scan(code or ""):
            cwe_counter.update(lr.get("cwe", []))
    cwe_frequency = [{"cwe": k, "count": v} for k, v in cwe_counter.most_common(10)]

    return {
        "total_scans": total,
        "risk_distribution": risk_dist,
        "verdict_distribution": verdict_dist,
        "source_distribution": source_dist,
        "project_distribution": project_dist,
        "cwe_frequency": cwe_frequency,
    }


@router.get("/model-performance")
def model_performance():
    if not os.path.exists(TRAINING_METADATA_PATH):
        return {"available": False}
    with open(TRAINING_METADATA_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    meta["available"] = True
    return meta


@functools.lru_cache(maxsize=1)
def _dataset_stats_cached():
    if not os.path.exists(DEVIGN_CLEANED_PATH):
        return {"available": False}
    import pandas as pd
    df = pd.read_csv(DEVIGN_CLEANED_PATH, usecols=lambda c: c in ("target", "project"))
    stats = {
        "available": True,
        "total_functions": int(len(df)),
        "vulnerable": int((df["target"] == 1).sum()) if "target" in df.columns else None,
        "safe": int((df["target"] == 0).sum()) if "target" in df.columns else None,
    }
    if "project" in df.columns:
        stats["by_project"] = df["project"].value_counts().to_dict()
    return stats


@router.get("/dataset-stats")
def dataset_stats():
    return _dataset_stats_cached()


@router.get("/pca-background")
def pca_background():
    bg = ml_bridge.pca_background()
    if bg is None:
        return {"available": False, "points": []}
    return {"available": True, **bg}


_MAX_DANGEROUS_SAMPLES_PER_DAY = 40


@router.get("/trends")
def security_trends(days: int = 14, db: Session = Depends(get_db)):
    """
    Day-by-day risk, complexity, and dangerous-API trend for the Security
    Dashboard. Complexity is read from each scan's ALREADY-STORED AST
    features (no reparsing, always exact). The dangerous-API count reruns
    the existing regex-based line_risk_scan over each scan's stored code --
    no tree-sitter reparsing, no model involvement -- but that regex pass
    is measurably not free at scale (profiled at ~11ms/record; a day with
    hundreds of scans would otherwise cost seconds on every single request).
    Capped at _MAX_DANGEROUS_SAMPLES_PER_DAY samples per day and scaled back
    up to an estimated day total -- exact when a day has fewer scans than
    the cap (the common case), a proportional estimate otherwise. avg_risk/
    avg_confidence/avg_complexity are unaffected -- those come from the
    already-stored numeric columns and stay exact over every scan.
    """
    import datetime as dt

    since = dt.datetime.utcnow() - dt.timedelta(days=days)
    rows = (
        db.query(ScanRecord.created_at, ScanRecord.vuln_probability, ScanRecord.confidence,
                  ScanRecord.ast_features_json, ScanRecord.code)
        .filter(ScanRecord.created_at >= since)
        .order_by(ScanRecord.created_at.asc())
        .all()
    )

    by_day = {}
    for created_at, vuln_prob, confidence, ast_json, code in rows:
        day = created_at.strftime("%Y-%m-%d")
        bucket = by_day.setdefault(day, {"risks": [], "confidences": [], "depths": [], "dangerous": 0, "dangerous_sampled": 0})
        bucket["risks"].append(vuln_prob or 0.0)
        bucket["confidences"].append(confidence or 0.0)
        try:
            ast_feats = json.loads(ast_json or "{}")
            bucket["depths"].append(ast_feats.get("max_depth", 0))
        except Exception:
            pass
        if bucket["dangerous_sampled"] < _MAX_DANGEROUS_SAMPLES_PER_DAY:
            try:
                bucket["dangerous"] += len(ml_bridge.line_risk_scan(code or ""))
                bucket["dangerous_sampled"] += 1
            except Exception:
                pass

    trend = []
    for i in range(days - 1, -1, -1):
        day = (dt.datetime.utcnow() - dt.timedelta(days=i)).strftime("%Y-%m-%d")
        b = by_day.get(day)
        scans_that_day = len(b["risks"]) if b else 0
        sampled = b["dangerous_sampled"] if b else 0
        # Exact when the day's scan count is within the sample cap (the
        # common case); otherwise scale the sampled sum up to an estimated
        # day total rather than silently under-reporting a busy day.
        dangerous_apis = round(b["dangerous"] * scans_that_day / sampled) if b and sampled else 0
        trend.append({
            "date": day,
            "avg_risk": round(sum(b["risks"]) / len(b["risks"]), 1) if b and b["risks"] else 0,
            "avg_confidence": round(sum(b["confidences"]) / len(b["confidences"]), 1) if b and b["confidences"] else 0,
            "avg_complexity": round(sum(b["depths"]) / len(b["depths"]), 1) if b and b["depths"] else 0,
            "dangerous_apis": dangerous_apis,
            "scans": scans_that_day,
        })
    return {"trend": trend}


@router.get("/feature-radar")
def aggregate_feature_radar(db: Session = Depends(get_db)):
    """Average AST + metric feature values across recent scans, for the
    Security Dashboard's radar chart. Reuses already-stored feature JSON --
    no reparsing."""
    rows = (
        db.query(ScanRecord.ast_features_json, ScanRecord.metric_features_json)
        .order_by(ScanRecord.created_at.desc())
        .limit(200)
        .all()
    )
    if not rows:
        return {"available": False, "ast_features": {}, "metric_features": {}}

    ast_sum, metric_sum = {}, {}
    n = 0
    for ast_json, metric_json in rows:
        try:
            ast_feats = json.loads(ast_json or "{}")
            metric_feats = json.loads(metric_json or "{}")
        except Exception:
            continue
        n += 1
        for k, v in ast_feats.items():
            ast_sum[k] = ast_sum.get(k, 0) + v
        for k, v in metric_feats.items():
            metric_sum[k] = metric_sum.get(k, 0) + v

    if n == 0:
        return {"available": False, "ast_features": {}, "metric_features": {}}

    return {
        "available": True,
        "sample_size": n,
        "ast_features": {k: round(v / n, 2) for k, v in ast_sum.items()},
        "metric_features": {k: round(v / n, 2) for k, v in metric_sum.items()},
    }


@router.get("/code-health")
def code_health(db: Session = Depends(get_db)):
    """
    Phase 3, item 2 (SOC dashboard): aggregate memory / buffer / pointer /
    leak counts across recent scans, for the dashboard's code-health panel.
    Re-runs the existing code_intelligence.analyze() over each scan's stored
    code (same function used everywhere else) -- no new detector, no schema
    change. Capped to the most recent 40 scans as a perf bound.
    """
    import code_intelligence

    rows = (
        db.query(ScanRecord.code)
        .order_by(ScanRecord.created_at.desc())
        .limit(40)
        .all()
    )
    if not rows:
        return {
            "available": False, "files_analyzed": 0,
            "memory_issues": 0, "buffer_issues": 0, "pointer_issues": 0, "leaks": 0,
            "functions_analyzed": 0, "total_dangerous_apis": 0,
        }

    memory_issues = buffer_issues = pointer_issues = leaks = 0
    functions_analyzed = total_dangerous_apis = 0
    analyzed = 0

    for (code,) in rows:
        intel = code_intelligence.analyze(code or "", vuln_probability=0.0)
        if not intel.get("available"):
            continue
        analyzed += 1
        functions_analyzed += intel.get("function_count", 0)
        total_dangerous_apis += len(intel.get("dangerous_apis", []))

        mem = intel.get("memory", {})
        if mem.get("potential_leak"):
            leaks += 1
        if mem.get("allocations", 0) != mem.get("frees", 0):
            memory_issues += 1

        buffer_issues += len(intel.get("buffers", []))

        pointers = intel.get("pointers", {})
        if pointers.get("dereferences", 0) > 0 and pointers.get("null_check_coverage_pct", 100) < 100:
            pointer_issues += 1

    return {
        "available": True,
        "files_analyzed": analyzed,
        "functions_analyzed": functions_analyzed,
        "memory_issues": memory_issues,
        "buffer_issues": buffer_issues,
        "pointer_issues": pointer_issues,
        "leaks": leaks,
        "total_dangerous_apis": total_dangerous_apis,
    }


@router.get("/scorecard")
def scorecard(db: Session = Depends(get_db)):
    """Enterprise Security Scorecard (Phase 5, priority #5) -- see scorecard.py."""
    import scorecard as scorecard_module
    return scorecard_module.compute_scorecard(db)
