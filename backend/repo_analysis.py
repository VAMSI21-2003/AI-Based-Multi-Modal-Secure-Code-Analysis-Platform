# =============================================================================
# repo_analysis.py -- shared, lightweight repository-level rollup helpers.
# Extracted so both export_center.py (Executive PDF) and routers/project.py
# (Project Scanner summary/knowledge-graph) compute folder-level scores the
# exact same way -- one calculation, reused, instead of two copies that
# could silently drift apart.
# =============================================================================

import re
from collections import defaultdict

RISK_RANK = {"SAFE": 0, "LOW RISK": 1, "MEDIUM RISK": 2, "HIGH RISK": 3, "CRITICAL": 4}


def folder_scores(files: list) -> list:
    """
    Every ancestor folder of every scanned file accumulates that file's
    vuln_probability -- same rollup rule as File Explorer's client-side
    computeFolderScores (average risk of everything beneath a folder).
    Returns rows sorted worst-first, so folder_scores(files)[0] is the
    single most dangerous folder (if files is non-empty).
    """
    stats = defaultdict(lambda: {"sum": 0.0, "count": 0, "worst_rank": -1, "worst": "SAFE"})
    for f in files:
        parts = re.split(r"[\\/]", f["filename"])
        for i in range(len(parts) - 1):
            folder = "/".join(parts[: i + 1])
            st = stats[folder]
            st["sum"] += f["vuln_probability"]
            st["count"] += 1
            rank = RISK_RANK.get(f["risk_level"], 0)
            if rank > st["worst_rank"]:
                st["worst_rank"] = rank
                st["worst"] = f["risk_level"]
    rows = [
        {"folder": folder, "avg_risk": st["sum"] / st["count"], "worst_risk": st["worst"], "file_count": st["count"]}
        for folder, st in stats.items() if st["count"] > 0
    ]
    rows.sort(key=lambda r: -r["avg_risk"])
    return rows
