# =============================================================================
# search_service.py -- Vulnerability Search Engine (Phase 3, #18).
#
# Searches across every STORED scan's real code/line-risk/AST output for a
# keyword, scoped by category (CWE / API / function / variable / pointer /
# loop / risk). Nothing here is precomputed or cached at scan time -- it
# re-runs the SAME existing analysis functions (ml_bridge.line_risk_scan,
# code_intelligence.analyze) already used everywhere else in the app, over
# a capped window of the most recent scans (perf bound for an on-demand,
# not-indexed search). No new model, no schema change.
# =============================================================================

import re

from sqlalchemy.orm import Session
from sqlalchemy import or_

import ml_bridge
import code_intelligence
from database import ScanRecord

MAX_SCANS_SEARCHED = 40
MAX_RESULTS = 60


def _word_matches(text: str, query: str) -> list:
    """Returns 1-indexed line numbers where `query` appears as a substring (case-insensitive)."""
    lines = text.split("\n")
    ql = query.lower()
    return [i + 1 for i, line in enumerate(lines) if ql in line.lower()]


def search(db: Session, query: str, category: str = "all") -> dict:
    query = (query or "").strip()
    if not query:
        return {"query": query, "category": category, "scanned": 0, "results": []}

    rows = (
        db.query(ScanRecord)
        .order_by(ScanRecord.created_at.desc())
        .limit(MAX_SCANS_SEARCHED)
        .all()
    )

    results = []
    ql = query.lower()

    for r in rows:
        code = r.code or ""
        matches = []

        if category in ("all", "cwe"):
            cwe_query = query.upper().replace("CWE", "CWE-").replace("--", "-").strip()
            for lr in ml_bridge.line_risk_scan(code):
                if any(ql in c.lower() or cwe_query == c for c in lr.get("cwe", [])):
                    matches.append({"kind": "cwe", "line": lr["line"], "detail": "; ".join(lr["reasons"]), "cwe": lr["cwe"]})

        if category in ("all", "api"):
            for name, (sev, cwe, desc) in code_intelligence.DANGEROUS_APIS.items():
                if ql in name.lower():
                    for line_no in _word_matches(code, name + "("):
                        matches.append({"kind": "api", "line": line_no, "detail": f"`{name}()` -- {desc or 'dangerous API'}", "cwe": [cwe] if cwe else []})

        if category in ("all", "risk"):
            if ql in (r.risk_level or "").lower() or ql in (r.risk_tag or "").lower() or ql in (r.verdict or "").lower():
                matches.append({"kind": "risk", "line": None, "detail": f"{r.verdict} -- {r.risk_level}", "cwe": []})

        if category in ("all", "function", "variable", "pointer", "loop"):
            intel = code_intelligence.analyze(code, vuln_probability=r.vuln_probability or 0.0)
            if intel.get("available"):
                if category in ("all", "function"):
                    for f in intel["functions"]:
                        if ql in f["name"].lower():
                            matches.append({"kind": "function", "line": f["start_line"], "detail": f["summary"], "cwe": []})
                if category in ("all", "pointer") and ("pointer" in ql or category == "pointer"):
                    if intel["pointers"]["pointer_variables"] > 0:
                        matches.append({
                            "kind": "pointer", "line": None,
                            "detail": f"{intel['pointers']['pointer_variables']} pointer variable(s), {intel['pointers']['dereferences']} dereference(s), {intel['pointers']['null_check_coverage_pct']}% NULL-checked",
                            "cwe": [],
                        })
                if category in ("all", "loop") and ("loop" in ql or category == "loop"):
                    for loop in intel["loops"]:
                        if ql in loop["condition_preview"].lower() or category == "loop":
                            matches.append({"kind": "loop", "line": loop["line"], "detail": f"{loop['type']} loop -- {loop['condition_preview']}" + (" (possibly infinite)" if loop["possibly_infinite"] else ""), "cwe": []})
                if category == "variable":
                    for mv in intel["variables"].get("most_mutated", []):
                        if ql in mv["name"].lower():
                            matches.append({"kind": "variable", "line": None, "detail": f"`{mv['name']}` mutated {mv['count']} time(s)", "cwe": []})

        if matches:
            results.append({
                "scan_id": r.id, "filename": r.filename, "project_name": r.project_name,
                "risk_level": r.risk_level, "verdict": r.verdict, "created_at": r.created_at.isoformat() + "Z",
                "matches": matches[:8],
            })
        if len(results) >= MAX_RESULTS:
            break

    return {"query": query, "category": category, "scanned": len(rows), "results": results}
