# =============================================================================
# ci_scan.py -- standalone CLI wrapper for CI/CD (Phase 4, Feature 7).
#
# Runs the EXISTING, unmodified prediction pipeline (ml_bridge.run_prediction,
# the same function every API endpoint uses) over every .c/.cpp/.h file
# under a target directory, with no FastAPI server and no database --
# suited to a GitHub Actions runner. Writes a Markdown report + a JSON
# summary, and exits non-zero if any CRITICAL-risk file is found (so it can
# gate a CI pipeline), unless --no-fail is passed.
#
# Usage:
#   python ci_scan.py --path . --output security-report --model XGBoost
# =============================================================================

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ml_bridge  # noqa: E402

CODE_EXTENSIONS = (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp")
MAX_FILE_SIZE = 512_000


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


def main():
    parser = argparse.ArgumentParser(description="SecureCode AI -- CI vulnerability scan")
    parser.add_argument("--path", default=".", help="Directory to scan recursively (default: current directory)")
    parser.add_argument("--output", default="security-report", help="Output file base name (writes .md and .json)")
    parser.add_argument("--model", default="XGBoost", choices=["XGBoost", "Random Forest"])
    parser.add_argument("--no-fail", action="store_true", help="Always exit 0, even if a --fail-on risk level is found")
    parser.add_argument(
        "--fail-on", default="CRITICAL",
        help="Comma-separated risk levels that fail the run, e.g. 'CRITICAL,HIGH RISK' (default: CRITICAL only). "
             "CRITICAL-only is the default because this is a research-scale classifier (measured F1=0.567, "
             "see paper/research_paper.md) -- gating on HIGH RISK too would fail CI on the model's real, "
             "documented false-positive rate rather than on high-confidence findings.",
    )
    args = parser.parse_args()
    fail_levels = {lvl.strip().upper() for lvl in args.fail_on.split(",") if lvl.strip()}

    files = sorted(find_source_files(args.path))
    results = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                code = fh.read()
        except OSError:
            continue
        if not code.strip():
            continue
        is_valid, _ = ml_bridge.validate_code(code)
        if not is_valid:
            continue
        r = ml_bridge.run_prediction(code, args.model)
        rel = os.path.relpath(path, args.path)
        results.append({
            "file": rel, "verdict": r["verdict"], "risk_level": r["risk_level"],
            "vuln_probability": round(r["vuln_probability"], 2), "confidence": round(r["confidence"], 2),
        })
        print(f"  {rel}: {r['verdict']} ({r['risk_level']}, {r['vuln_probability']:.1f}%)")

    total = len(results)
    vulnerable = sum(1 for r in results if r["verdict"] == "VULNERABLE")
    by_risk = {"CRITICAL": 0, "HIGH RISK": 0, "MEDIUM RISK": 0, "LOW RISK": 0, "SAFE": 0}
    for r in results:
        by_risk[r["risk_level"]] = by_risk.get(r["risk_level"], 0) + 1
    critical = by_risk["CRITICAL"]
    avg_risk = round(sum(r["vuln_probability"] for r in results) / total, 2) if total else 0.0
    top_risky = sorted(results, key=lambda r: -r["vuln_probability"])[:10]
    failing_files = [r for r in results if r["risk_level"] in fail_levels]

    summary = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scanned_path": os.path.abspath(args.path),
        "total_files": total,
        "vulnerable_files": vulnerable,
        "safe_files": total - vulnerable,
        "critical_files": critical,
        "risk_breakdown": by_risk,
        "average_risk_percent": avg_risk,
        "model": args.model,
        "fail_policy": sorted(fail_levels),
        "failing_files": len(failing_files),
        "results": results,
    }

    with open(f"{args.output}.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    md = [
        "# SecureCode AI -- CI Security Report", "",
        f"Generated {summary['generated']} &middot; model: {args.model}", "",
        f"| Files Scanned | Vulnerable | Safe | Critical | High | Medium | Low | Avg. Risk |",
        f"|---|---|---|---|---|---|---|---|",
        f"| {total} | {vulnerable} | {total - vulnerable} | {by_risk['CRITICAL']} | {by_risk['HIGH RISK']} | "
        f"{by_risk['MEDIUM RISK']} | {by_risk['LOW RISK']} | {avg_risk}% |",
        "",
        f"**CI fail policy:** fails the build on: {', '.join(sorted(fail_levels)) or '(none -- report only)'}",
        "", "## Top Risky Files", "",
        "| File | Verdict | Risk Level | Probability |",
        "|---|---|---|---|",
    ]
    for r in top_risky:
        flag = " ⚠️" if r["risk_level"] in fail_levels else ""
        md.append(f"| `{r['file']}` | {r['verdict']} | {r['risk_level']}{flag} | {r['vuln_probability']}% |")
    if total == 0:
        md.append("")
        md.append("_No .c/.cpp/.h files found under the scanned path._")
    with open(f"{args.output}.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")

    print(f"\n{total} file(s) scanned, {vulnerable} vulnerable, {critical} critical. Avg risk {avg_risk}%.")
    print(f"Report written to {args.output}.md / {args.output}.json")

    if failing_files and not args.no_fail:
        print(f"FAILING: {len(failing_files)} file(s) at or above the fail policy ({', '.join(sorted(fail_levels))}).")
        sys.exit(1)


if __name__ == "__main__":
    main()
