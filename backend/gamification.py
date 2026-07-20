# =============================================================================
# gamification.py -- Security Gamification (Phase 3, item 17).
#
# Every badge/achievement/tier below is computed directly from real
# ScanRecord rows -- no mock values, no fabricated statistics. A badge is
# either earned (its condition is true against the actual scan history) or
# it isn't; there is no "sample" or "demo" state. Purely additive: reads
# ScanRecord, writes nothing, touches no other module.
# =============================================================================

import datetime as dt

from sqlalchemy.orm import Session
from sqlalchemy import func

from database import ScanRecord

TIERS = [
    {"name": "Bronze", "min_score": 0, "color": "#c98136"},
    {"name": "Silver", "min_score": 40, "color": "#9aa3ad"},
    {"name": "Gold", "min_score": 60, "color": "#e0b13c"},
    {"name": "Platinum", "min_score": 80, "color": "#7fd8e8"},
]


def _tier_for(score: float) -> dict:
    tier = TIERS[0]
    for t in TIERS:
        if score >= t["min_score"]:
            tier = t
    return tier


def _longest_clean_streak(verdicts_in_order: list) -> int:
    longest = current = 0
    for v in verdicts_in_order:
        if v != "VULNERABLE":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def compute_status(db: Session) -> dict:
    total = db.query(func.count(ScanRecord.id)).scalar() or 0

    if total == 0:
        return {
            "total_scans": 0, "security_score": 0, "tier": TIERS[0], "next_tier": TIERS[1],
            "progress_to_next": 0.0, "badges": [], "badges_earned": 0, "badges_total": 0,
        }

    vulnerable = db.query(func.count(ScanRecord.id)).filter(ScanRecord.verdict == "VULNERABLE").scalar() or 0
    avg_vuln_prob = db.query(func.avg(ScanRecord.vuln_probability)).scalar() or 0.0
    security_score = round(max(0.0, 100.0 - avg_vuln_prob), 1)

    critical_count = db.query(func.count(ScanRecord.id)).filter(ScanRecord.risk_level == "CRITICAL").scalar() or 0
    distinct_projects = db.query(func.count(func.distinct(ScanRecord.project_name))).scalar() or 0
    batch_scans = db.query(func.count(func.distinct(ScanRecord.batch_id))).filter(ScanRecord.batch_id.isnot(None)).scalar() or 0
    github_scans = db.query(func.count(ScanRecord.id)).filter(ScanRecord.batch_id.like("gh_%")).scalar() or 0
    watch_scans = db.query(func.count(ScanRecord.id)).filter(ScanRecord.source == "watch").scalar() or 0
    pinned_count = db.query(func.count(ScanRecord.id)).filter(ScanRecord.is_pinned == 1).scalar() or 0

    ordered_verdicts = [v for (v,) in db.query(ScanRecord.verdict).order_by(ScanRecord.created_at.asc()).all()]
    clean_streak = _longest_clean_streak(ordered_verdicts)

    oldest = db.query(func.min(ScanRecord.created_at)).scalar()
    days_active = (dt.datetime.utcnow() - oldest).days + 1 if oldest else 0

    badges = [
        {"id": "first-scan", "name": "First Scan", "description": "Ran your very first scan.", "icon": "shield-check",
         "earned": total >= 1, "progress": min(total, 1), "target": 1},
        {"id": "getting-started", "name": "Getting Started", "description": "Scanned 10 files.", "icon": "target",
         "earned": total >= 10, "progress": min(total, 10), "target": 10},
        {"id": "century-club", "name": "Century Club", "description": "Scanned 100 files.", "icon": "award",
         "earned": total >= 100, "progress": min(total, 100), "target": 100},
        {"id": "bug-hunter", "name": "Bug Hunter", "description": "Found 5 vulnerable files.", "icon": "bug",
         "earned": vulnerable >= 5, "progress": min(vulnerable, 5), "target": 5},
        {"id": "bug-hunter-2", "name": "Bug Hunter II", "description": "Found 25 vulnerable files.", "icon": "bug",
         "earned": vulnerable >= 25, "progress": min(vulnerable, 25), "target": 25},
        {"id": "critical-catcher", "name": "Critical Catcher", "description": "Caught a CRITICAL-risk file before it shipped.", "icon": "flame",
         "earned": critical_count >= 1, "progress": min(critical_count, 1), "target": 1},
        {"id": "clean-streak", "name": "Clean Streak", "description": "5 consecutive NOT VULNERABLE scans.", "icon": "sparkles",
         "earned": clean_streak >= 5, "progress": min(clean_streak, 5), "target": 5},
        {"id": "multi-project", "name": "Multi-Project", "description": "Scanned across 3 or more distinct projects.", "icon": "folder-git",
         "earned": distinct_projects >= 3, "progress": min(distinct_projects, 3), "target": 3},
        {"id": "batch-master", "name": "Batch Master", "description": "Ran a multi-file project scan.", "icon": "layers",
         "earned": batch_scans >= 1, "progress": min(batch_scans, 1), "target": 1},
        {"id": "github-explorer", "name": "GitHub Explorer", "description": "Scanned a cloned GitHub repository.", "icon": "git-fork",
         "earned": github_scans >= 1, "progress": min(github_scans, 1), "target": 1},
        {"id": "live-guardian", "name": "Live Guardian", "description": "Used Watch Mode to catch a live change.", "icon": "eye",
         "earned": watch_scans >= 1, "progress": min(watch_scans, 1), "target": 1},
        {"id": "curator", "name": "Curator", "description": "Pinned a scan for later reference.", "icon": "pin",
         "earned": pinned_count >= 1, "progress": min(pinned_count, 1), "target": 1},
        {"id": "safety-champion", "name": "Safety Champion", "description": "Average security score above 70 across 5+ scans.", "icon": "shield",
         "earned": total >= 5 and security_score >= 70, "progress": security_score if total >= 5 else 0, "target": 70},
    ]

    tier = _tier_for(security_score)
    tier_idx = TIERS.index(tier)
    next_tier = TIERS[tier_idx + 1] if tier_idx + 1 < len(TIERS) else None
    if next_tier:
        span = next_tier["min_score"] - tier["min_score"]
        progress_to_next = round(((security_score - tier["min_score"]) / span) * 100, 1) if span else 100.0
    else:
        progress_to_next = 100.0

    return {
        "total_scans": total,
        "vulnerable_scans": vulnerable,
        "security_score": security_score,
        "days_active": days_active,
        "clean_streak": clean_streak,
        "tier": tier,
        "next_tier": next_tier,
        "progress_to_next": progress_to_next,
        "badges": badges,
        "badges_earned": sum(1 for b in badges if b["earned"]),
        "badges_total": len(badges),
    }
