# =============================================================================
# scorecard.py -- Enterprise Security Scorecard (Phase 5, priority #5).
#
# Distinct from gamification.py (which frames progress as badges/tiers for
# an individual user) -- this is an audit-style weighted rubric producing
# ONE letter grade (A-F) from several real, independently-computed factors,
# the way a security-ratings vendor (BitSight, SecurityScorecard) presents
# a portfolio score to an executive. Every factor is computed from data
# already produced elsewhere (ScanRecord aggregates, code_intelligence
# output) -- no new model, no fabricated sub-score.
# =============================================================================

import datetime as dt

from sqlalchemy.orm import Session
from sqlalchemy import func

from database import ScanRecord

FACTORS = [
    {"id": "vulnerability_density", "label": "Vulnerability Density", "weight": 0.30},
    {"id": "critical_exposure", "label": "Critical Exposure", "weight": 0.25},
    {"id": "code_quality", "label": "Code Quality", "weight": 0.20},
    {"id": "memory_safety", "label": "Memory Safety", "weight": 0.15},
    {"id": "remediation_trend", "label": "Remediation Trend", "weight": 0.10},
]


def _letter_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def compute_scorecard(db: Session) -> dict:
    import code_intelligence

    total = db.query(func.count(ScanRecord.id)).scalar() or 0
    if total == 0:
        return {
            "available": False, "overall_score": 0, "grade": "N/A", "factors": [],
            "total_scans": 0, "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    vulnerable = db.query(func.count(ScanRecord.id)).filter(ScanRecord.verdict == "VULNERABLE").scalar() or 0
    critical = db.query(func.count(ScanRecord.id)).filter(ScanRecord.risk_level == "CRITICAL").scalar() or 0

    # Vulnerability density: fraction of files NOT flagged vulnerable, scaled to 0-100.
    vuln_density_score = round(max(0.0, (1 - vulnerable / total)) * 100, 1)

    # Critical exposure: fraction of files that are NOT critical, scaled to 0-100
    # but weighted harshly -- even a small critical fraction should hurt the grade.
    critical_fraction = critical / total
    critical_exposure_score = round(max(0.0, 100 - critical_fraction * 400), 1)  # 25% critical -> 0

    # Code quality: average of code_intelligence's own "quality" composite score
    # (maintainability / complexity / nesting derived), over a bounded recent sample.
    rows = db.query(ScanRecord.code).order_by(ScanRecord.created_at.desc()).limit(40).all()
    quality_scores = []
    memory_penalty_total = 0
    memory_sample = 0
    for (code,) in rows:
        intel = code_intelligence.analyze(code or "", vuln_probability=0.0)
        if not intel.get("available"):
            continue
        quality_scores.append(intel["scores"]["quality"])
        memory_sample += 1
        mem = intel.get("memory", {})
        ptr = intel.get("pointers", {})
        penalty = 0
        if mem.get("potential_leak"):
            penalty += 20
        if mem.get("allocations", 0) != mem.get("frees", 0):
            penalty += 10
        if ptr.get("dereferences", 0) > 0 and ptr.get("null_check_coverage_pct", 100) < 50:
            penalty += 20
        memory_penalty_total += penalty
    code_quality_score = round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 50.0
    memory_safety_score = round(max(0.0, 100 - (memory_penalty_total / memory_sample)), 1) if memory_sample else 50.0

    # Remediation trend: same "first half vs second half" comparison already
    # used by the Security Dashboard page, reframed as a 0-100 sub-score
    # (improving risk -> higher score; worsening -> lower).
    ordered = db.query(ScanRecord.vuln_probability).order_by(ScanRecord.created_at.asc()).all()
    probs = [p for (p,) in ordered if p is not None]
    if len(probs) >= 4:
        half = len(probs) // 2
        first_avg = sum(probs[:half]) / half
        second_avg = sum(probs[half:]) / (len(probs) - half)
        delta = first_avg - second_avg  # positive = improving (risk went down)
        remediation_trend_score = round(max(0.0, min(100.0, 60 + delta)), 1)
    else:
        remediation_trend_score = 60.0  # neutral -- not enough history yet

    factor_scores = {
        "vulnerability_density": vuln_density_score,
        "critical_exposure": critical_exposure_score,
        "code_quality": code_quality_score,
        "memory_safety": memory_safety_score,
        "remediation_trend": remediation_trend_score,
    }

    overall = sum(factor_scores[f["id"]] * f["weight"] for f in FACTORS)
    overall = round(overall, 1)

    factors_out = [
        {**f, "score": factor_scores[f["id"]], "grade": _letter_grade(factor_scores[f["id"]])}
        for f in FACTORS
    ]

    return {
        "available": True,
        "overall_score": overall,
        "grade": _letter_grade(overall),
        "factors": factors_out,
        "total_scans": total,
        "vulnerable_files": vulnerable,
        "critical_files": critical,
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
