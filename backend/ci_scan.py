# =============================================================================
# ci_scan.py -- standalone CLI wrapper for CI/CD (Phase 4, Feature 7).
#
# Runs the EXISTING, unmodified prediction pipeline (ml_bridge.run_prediction,
# the same function every API endpoint uses) over source files, with no
# FastAPI server and no database -- suited to a GitHub Actions runner. This
# is the LIVE, single-function inference path: AST + metrics + CodeBERT are
# computed directly from each file's own text and concatenated, with no
# cross-file positional join of the kind that corrupted the OFFLINE training
# fusion pipeline (see docs/ML_FORENSIC_AUDIT_PHASE4.md /
# docs/ML_ALIGNMENT_FIX_RESULTS.md) -- that bug never applied here.
#
# Two ways to choose what gets scanned:
#   --path DIR          walk DIR recursively for .c/.h/.cpp/.cc/.cxx/.hpp files
#   --files-from FILE    scan exactly the files listed (one per line, relative
#                        to --path) -- e.g. the output of `git diff --name-only`
#                        for a pull request, so CI can scan only changed files
#                        instead of a whole repository.
#
# Writes a Markdown report, a JSON summary, and a SARIF 2.1.0 file (for
# `github/codeql-action/upload-sarif`). Exits non-zero only if BOTH the scan
# found a finding at or above --fail-on AND blocking mode is on (--blocking,
# or the SCAN_BLOCKING env var) -- blocking is OFF by default, see
# docs/CI_CD.md for why.
#
# Usage:
#   python ci_scan.py --path . --output security-report
#   python ci_scan.py --files-from changed_files.txt --path .. --output ../security-report
# =============================================================================

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ml_bridge  # noqa: E402
import code_intelligence  # noqa: E402

CODE_EXTENSIONS = (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp")
MAX_FILE_SIZE = 512_000

RISK_LEVELS = ["SAFE", "LOW RISK", "MEDIUM RISK", "HIGH RISK", "CRITICAL"]
SARIF_LEVEL = {"CRITICAL": "error", "HIGH RISK": "warning", "MEDIUM RISK": "warning", "LOW RISK": "note", "SAFE": "note"}

BASELINE_STATUS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "ml_baseline_status.json"
)


def _env_flag(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def find_source_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "venv", "__pycache__", "dist", "build")]
        for name in filenames:
            if os.path.splitext(name)[1].lower() in CODE_EXTENSIONS:
                full = os.path.join(dirpath, name)
                try:
                    if os.path.getsize(full) <= MAX_FILE_SIZE:
                        yield full
                except OSError:
                    continue


def load_files_from_list(list_path: str, base_dir: str):
    """
    Read a newline-separated file list (e.g. `git diff --name-only` output)
    and resolve each entry against base_dir. Filters to CODE_EXTENSIONS,
    skips paths that don't exist (a deleted file in the diff) or are too
    large, exactly like find_source_files does for a directory walk.
    """
    with open(list_path, "r", encoding="utf-8") as fh:
        raw_lines = [line.strip() for line in fh]

    for line in raw_lines:
        if not line:
            continue
        full = line if os.path.isabs(line) else os.path.join(base_dir, line)
        if os.path.splitext(full)[1].lower() not in CODE_EXTENSIONS:
            continue
        if not os.path.isfile(full):
            continue  # deleted/renamed-away in this diff
        try:
            if os.path.getsize(full) > MAX_FILE_SIZE:
                continue
        except OSError:
            continue
        yield full


def load_baseline_status():
    """
    Reads models/ml_baseline_status.json -- a small, manually-maintained
    (see that file's own "maintained_by" field) status record of the ML
    fusion-alignment fix. Read here, not hand-typed into this script or the
    workflow YAML, specifically so the PR comment/summary can't silently go
    stale if the baseline status changes without this file being updated.
    Returns None if the file is missing (older checkout, or not yet created).
    """
    try:
        with open(BASELINE_STATUS_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def build_function_index(code: str):
    """
    Returns [(start_line, end_line, name), ...] for every function_definition
    in `code`, reusing code_intelligence's existing tree-sitter-based function
    discovery (the same parser AST feature extraction already uses) rather
    than reimplementing C parsing here. Returns [] if tree-sitter isn't
    available or the code doesn't parse -- callers must treat "no function
    found" as a normal, honest outcome, not an error.
    """
    try:
        root, source = code_intelligence.parse(code)
        if root is None:
            return []
        index = []
        for fn in code_intelligence.find_functions(root):
            name = code_intelligence._function_name(fn, source)
            index.append((fn.start_point[0] + 1, fn.end_point[0] + 1, name))
        return index
    except Exception:
        return []


def function_at_line(index, line_no):
    for start, end, name in index:
        if start <= line_no <= end:
            return name
    return None


def scan_one_file(path: str, base_dir: str, model_choice: str):
    """
    Runs the live inference pipeline plus the deterministic line-level
    evidence scan against a single file, and reconciles them via
    ml_bridge.evidence_based_risk() (already-tested logic, not duplicated
    here) so the combined risk level can only be escalated by evidence, never
    suppressed. Returns None for empty/invalid files (skipped, not an error).
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            code = fh.read()
    except OSError:
        return None
    if not code.strip():
        return None
    is_valid, _ = ml_bridge.validate_code(code)
    if not is_valid:
        return None

    r = ml_bridge.run_prediction(code, model_choice)
    model_mode = "fallback" if r.get("is_demo") else "trained"

    line_risks = ml_bridge.line_risk_scan(code)
    combined = ml_bridge.evidence_based_risk(r["risk_level"], line_risks)
    fn_index = build_function_index(code)
    rel = os.path.relpath(path, base_dir).replace(os.sep, "/")

    findings = []
    for item in combined["reasons"]:
        findings.append({
            "line": item["line"],
            "function": function_at_line(fn_index, item["line"]),
            "cwe": [item["cwe"]] if item["cwe"] else [],
            "evidence": item["reason"],
        })
    if not findings and combined["level"] != "SAFE":
        # ML flagged this file/function as elevated risk but no specific
        # dangerous-pattern line matched -- report it as a file-level
        # finding (line 1) instead of silently dropping it.
        findings.append({
            "line": 1,
            "function": None,
            "cwe": [],
            "evidence": "ML classifier flagged this file as elevated risk; no specific line-level pattern matched "
                        f"(vuln_probability={round(r['vuln_probability'], 2)}%).",
        })

    return {
        "file": rel,
        "verdict": r["verdict"],
        "model_used": r["model_used"],
        "model_mode": model_mode,
        "ml_risk_level": r["risk_level"],
        "ml_vuln_probability": round(r["vuln_probability"], 2),
        "combined_risk_level": combined["level"],
        "escalated_by_evidence": combined["escalated"],
        "findings": findings,
    }


def to_sarif(file_results: list, files_scanned_path: str) -> dict:
    rules = {}
    results = []
    for fr in file_results:
        level = SARIF_LEVEL.get(fr["combined_risk_level"], "warning")
        for f in fr["findings"]:
            rule_id = f["cwe"][0] if f["cwe"] else "SCAN-ML-FINDING"
            if rule_id not in rules:
                cwe_num = rule_id.split("-", 1)[1] if rule_id.startswith("CWE-") else None
                rules[rule_id] = {
                    "id": rule_id,
                    "name": rule_id.replace("-", "_"),
                    "shortDescription": {"text": f["evidence"][:120]},
                    "helpUri": f"https://cwe.mitre.org/data/definitions/{cwe_num}.html" if cwe_num else None,
                }
            results.append({
                "ruleId": rule_id,
                "level": level,
                "message": {
                    "text": f"{f['evidence']} [model={fr['model_used']}, mode={fr['model_mode']}, "
                            f"ml_vuln_probability={fr['ml_vuln_probability']}%]"
                },
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": fr["file"]},
                        "region": {"startLine": max(1, f["line"])},
                    }
                }],
            })

    rule_list = []
    for rule in rules.values():
        if rule["helpUri"] is None:
            rule.pop("helpUri")
        rule_list.append(rule)

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "SecureCode-AI-CI-Scan",
                    "version": "1.0.0",
                    "rules": rule_list,
                }
            },
            "results": results,
        }],
    }


def main():
    parser = argparse.ArgumentParser(description="SecureCode AI -- CI vulnerability scan")
    parser.add_argument("--path", default=".", help="Directory to scan (full walk), or the base directory --files-from paths are relative to")
    parser.add_argument("--files-from", default=None, help="Path to a newline-separated file list (e.g. `git diff --name-only` output) to scan instead of walking --path")
    parser.add_argument("--output", default="security-report", help="Output file base name (writes .md, .json, .sarif)")
    parser.add_argument("--model", default="XGBoost", choices=["XGBoost", "Random Forest"])
    parser.add_argument("--no-fail", action="store_true", help="Always exit 0 regardless of --blocking/SCAN_BLOCKING")
    parser.add_argument("--fail-on", default="CRITICAL", help="Comma-separated combined risk levels that fail the run when blocking is on, e.g. 'CRITICAL,HIGH RISK' (default: CRITICAL only)")
    blocking_group = parser.add_mutually_exclusive_group()
    blocking_group.add_argument("--blocking", dest="blocking", action="store_true", default=None, help="Fail the process (exit 1) if a --fail-on finding is present. Overrides SCAN_BLOCKING.")
    blocking_group.add_argument("--non-blocking", dest="blocking", action="store_false", help="Never fail the process, only report. Overrides SCAN_BLOCKING.")
    args = parser.parse_args()

    blocking = args.blocking if args.blocking is not None else _env_flag("SCAN_BLOCKING", default=False)
    fail_levels = {lvl.strip().upper() for lvl in args.fail_on.split(",") if lvl.strip()}

    if args.files_from:
        file_iter = load_files_from_list(args.files_from, args.path)
    else:
        file_iter = find_source_files(args.path)
    files = sorted(set(file_iter))

    file_results = []
    for path in files:
        r = scan_one_file(path, args.path, args.model)
        if r is None:
            continue
        file_results.append(r)
        flag = " [FLAGGED]" if r["combined_risk_level"] in fail_levels else ""
        print(f"  {r['file']}: {r['verdict']} ({r['combined_risk_level']}{flag}, {r['ml_vuln_probability']}%, model={r['model_used']} [{r['model_mode']}])")

    total = len(file_results)
    vulnerable = sum(1 for r in file_results if r["verdict"] == "VULNERABLE")
    by_risk = {lvl: 0 for lvl in RISK_LEVELS}
    for r in file_results:
        by_risk[r["combined_risk_level"]] = by_risk.get(r["combined_risk_level"], 0) + 1
    avg_risk = round(sum(r["ml_vuln_probability"] for r in file_results) / total, 2) if total else 0.0
    top_risky = sorted(file_results, key=lambda r: -r["ml_vuln_probability"])[:10]
    failing_files = [r for r in file_results if r["combined_risk_level"] in fail_levels]

    modes_seen = {r["model_mode"] for r in file_results}
    if not modes_seen:
        overall_model_mode = "n/a (no files scanned)"
    elif len(modes_seen) == 1:
        overall_model_mode = next(iter(modes_seen))
    else:
        overall_model_mode = "mixed"

    baseline_status = load_baseline_status()
    if baseline_status:
        baseline_line = (
            f"{baseline_status.get('baseline_go_no_go', 'UNKNOWN')} -- "
            f"fusion alignment: {baseline_status.get('fusion_alignment_status', 'unknown')} "
            f"(threshold={baseline_status.get('decision_threshold', '?')})"
        )
    else:
        baseline_line = "UNKNOWN -- models/ml_baseline_status.json not found in this checkout"

    summary = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scan_mode": "changed-files" if args.files_from else "full-path",
        "scanned_path": os.path.abspath(args.path),
        "total_files": total,
        "vulnerable_files": vulnerable,
        "safe_files": total - vulnerable,
        "risk_breakdown": by_risk,
        "average_ml_vuln_probability": avg_risk,
        "model": args.model,
        "model_mode": overall_model_mode,
        "fail_policy": sorted(fail_levels),
        "blocking": blocking,
        "failing_files": len(failing_files),
        "ml_baseline_status": baseline_status,
        "ml_baseline_status_line": baseline_line,
        "results": file_results,
    }

    with open(f"{args.output}.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    with open(f"{args.output}.sarif", "w", encoding="utf-8") as fh:
        json.dump(to_sarif(file_results, args.path), fh, indent=2)

    md = [
        "# SecureCode AI -- CI Security Report", "",
        f"Generated {summary['generated']} &middot; mode: {summary['scan_mode']} &middot; model: {args.model} "
        f"&middot; model_mode: **{overall_model_mode}**",
        "",
        f"**ML baseline status:** {baseline_line}",
        "",
        f"**Blocking:** {'YES' if blocking else 'NO (report-only)'} &middot; "
        f"**fail policy:** {', '.join(sorted(fail_levels)) or '(none)'}",
        "",
        f"| Files Scanned | Vulnerable | Safe | Critical | High | Medium | Low | Avg. ML Risk |",
        f"|---|---|---|---|---|---|---|---|",
        f"| {total} | {vulnerable} | {total - vulnerable} | {by_risk['CRITICAL']} | {by_risk['HIGH RISK']} | "
        f"{by_risk['MEDIUM RISK']} | {by_risk['LOW RISK']} | {avg_risk}% |",
        "", "## Top Risky Files", "",
        "| File | Verdict | Combined Risk | ML Probability | Model Mode |",
        "|---|---|---|---|---|",
    ]
    for r in top_risky:
        flag = " ⚠️" if r["combined_risk_level"] in fail_levels else ""
        md.append(f"| `{r['file']}` | {r['verdict']} | {r['combined_risk_level']}{flag} | {r['ml_vuln_probability']}% | {r['model_mode']} |")
    if total == 0:
        md.append("")
        md.append("_No .c/.cpp/.h files matched the scan target (either an empty diff, or this checkout has no such files at that path)._")
    with open(f"{args.output}.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")

    print(f"\n{total} file(s) scanned, {vulnerable} vulnerable. Avg ML risk {avg_risk}%. Model mode: {overall_model_mode}.")
    print(f"Report written to {args.output}.md / {args.output}.json / {args.output}.sarif")

    if failing_files and blocking and not args.no_fail:
        print(f"FAILING: {len(failing_files)} file(s) at or above the fail policy ({', '.join(sorted(fail_levels))}), and blocking mode is ON.")
        sys.exit(1)
    elif failing_files:
        print(f"NOTE: {len(failing_files)} file(s) at or above the fail policy, but blocking mode is OFF -- not failing the build.")


if __name__ == "__main__":
    main()
