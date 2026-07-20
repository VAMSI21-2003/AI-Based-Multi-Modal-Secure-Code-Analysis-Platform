# =============================================================================
# routers/dashboard.py -- aggregate stats for the main Dashboard module.
# =============================================================================

import os
import json
import datetime as dt
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

import ml_bridge
from database import get_db, ScanRecord
from scan_service import record_to_dict

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    total_scans = db.query(func.count(ScanRecord.id)).scalar() or 0
    total_vulnerable = db.query(func.count(ScanRecord.id)).filter(
        ScanRecord.verdict == "VULNERABLE"
    ).scalar() or 0
    avg_vuln_prob = db.query(func.avg(ScanRecord.vuln_probability)).scalar() or 0.0
    avg_confidence = db.query(func.avg(ScanRecord.confidence)).scalar() or 0.0

    risk_counts = dict(
        db.query(ScanRecord.risk_level, func.count(ScanRecord.id))
        .group_by(ScanRecord.risk_level)
        .all()
    )

    # Most common vulnerability -- derived from stored AST/metric feature
    # signatures isn't a CWE, so we recompute the line-risk CWE tally over
    # the most recent vulnerable records (cheap regex scan, done lazily
    # here). Capped at 100 (was 300) -- profiled at ~11ms/record, so 300
    # records cost ~3.4s on every dashboard load once the DB accumulates a
    # few hundred scans; 100 recent records is still a representative
    # sample for "most common recent vulnerability" and cuts this to ~1.1s.
    vulnerable_records = (
        db.query(ScanRecord.code)
        .filter(ScanRecord.verdict == "VULNERABLE")
        .order_by(ScanRecord.created_at.desc())
        .limit(100)
        .all()
    )
    cwe_counter = Counter()
    for (code,) in vulnerable_records:
        for lr in ml_bridge.line_risk_scan(code or ""):
            cwe_counter.update(lr.get("cwe", []))
    most_common_cwe = cwe_counter.most_common(1)
    most_common = most_common_cwe[0][0] if most_common_cwe else None

    recent = (
        db.query(ScanRecord)
        .order_by(ScanRecord.created_at.desc())
        .limit(8)
        .all()
    )

    # 14-day trend
    since = dt.datetime.utcnow() - dt.timedelta(days=14)
    trend_rows = (
        db.query(ScanRecord.created_at, ScanRecord.verdict)
        .filter(ScanRecord.created_at >= since)
        .all()
    )
    by_day = Counter()
    vuln_by_day = Counter()
    for created_at, verdict in trend_rows:
        day = created_at.strftime("%Y-%m-%d")
        by_day[day] += 1
        if verdict == "VULNERABLE":
            vuln_by_day[day] += 1

    trend = []
    for i in range(13, -1, -1):
        day = (dt.datetime.utcnow() - dt.timedelta(days=i)).strftime("%Y-%m-%d")
        trend.append({"date": day, "scans": by_day.get(day, 0), "vulnerabilities": vuln_by_day.get(day, 0)})

    return {
        "total_files_scanned": total_scans,
        "total_vulnerabilities": total_vulnerable,
        "safe_count": total_scans - total_vulnerable,
        "risk_distribution": risk_counts,
        "most_common_vulnerability": most_common,
        "average_risk_percent": round(avg_vuln_prob, 2),
        "average_confidence_percent": round(avg_confidence, 2),
        "recent_scans": [record_to_dict(r, include_code=False) for r in recent],
        "trend_14d": trend,
        "models_status": ml_bridge.models_status(),
    }
