# =============================================================================
# copilot.py -- "AI Security Copilot": deterministic Q&A over the existing
# knowledge base, dangerous-API catalogue, and (optionally) a specific
# scan's own analysis. No external LLM call -- pattern/keyword matching over
# the SAME reference data already surfaced elsewhere in the app, consistent
# with the project's established "deterministic AI" approach.
#
# Phase 1 (Security Copilot) extends the original CWE/API Q&A with scan-aware
# intents: prediction/confidence explanation, per-branch (AST / Metrics /
# CodeBERT) contribution breakdown, line highlighting, fix suggestions,
# exploit/attacker-impact narrative, developer-mistake framing, severity and
# remediation-priority ranking, plus explicit OWASP / CERT-C / MITRE / CAPEC
# lookups. Everything is computed from data already produced elsewhere
# (ml_bridge, code_intelligence, recommendations, knowledge_base) -- no new
# model, no retraining, no external call.
# =============================================================================

import re

import knowledge_base
import code_intelligence
import ml_bridge
import recommendations

CWE_RE = re.compile(r"cwe-?\s?(\d+)", re.IGNORECASE)

# Maps a spoken/typed concept to the canonical dangerous-API name and/or CWE id.
API_ALIASES = {
    "strcpy": "strcpy", "strcat": "strcat", "gets": "gets", "sprintf": "sprintf",
    "vsprintf": "vsprintf", "scanf": "scanf", "alloca": "alloca", "system": "system",
    "popen": "popen", "exec": "exec", "memcpy": "memcpy", "memmove": "memmove",
    "strncpy": "strncpy", "malloc": "malloc", "calloc": "calloc", "realloc": "realloc",
    "free": "free", "atoi": "atoi", "rand": "rand",
}

CONCEPT_TO_CWE = {
    "buffer overflow": "CWE-120", "stack overflow": "CWE-120", "overflow": "CWE-120",
    "gets": "CWE-242",
    "integer overflow": "CWE-190", "wraparound": "CWE-190",
    "alloca": "CWE-770", "unbounded allocation": "CWE-770",
    "use after free": "CWE-416", "use-after-free": "CWE-416", "uaf": "CWE-416", "dangling pointer": "CWE-416", "double free": "CWE-416",
    "format string": "CWE-134",
    "command injection": "CWE-78", "shell injection": "CWE-78",
    "null termination": "CWE-170", "nul termination": "CWE-170",
    "out of bounds read": "CWE-125", "buffer over-read": "CWE-125", "over-read": "CWE-125",
    "null pointer": "CWE-476", "null dereference": "CWE-476", "segfault": "CWE-476", "segmentation fault": "CWE-476",
}

GREETINGS = {"hi", "hello", "hey", "help", "?", ""}

# Scan-aware intent keywords, checked in this order (most specific first).
LINE_WORDS = ("highlight", "which line", "what line", "line number", "vulnerable line")
FIX_WORDS = ("suggest a fix", "suggest fix", "how do i fix", "how to fix", "fix this", "secure code", "generate secure", "rewrite", "patch this")
CONFIDENCE_WORDS = ("confidence high", "confidence low", "why confidence", "how confident", "confidence score", "why is confidence", "why the confidence")
CODEBERT_WORDS = ("codebert", "embedding", "semantic")
METRICS_WORDS = ("metrics contribution", "software metrics", "metric branch", "quality metrics")
AST_WORDS = ("ast finding", "ast contribution", "structural feature", "abstract syntax", "ast branch")
EXPLOIT_WORDS = ("exploit", "attacker", "how could this be", "how would this be attacked", "attack scenario")
MISTAKE_WORDS = ("developer mistake", "what did the developer", "what went wrong", "coding mistake", "why did this happen")
PRIORITY_WORDS = ("priority", "what should i fix first", "remediation order", "fix order", "what first")
SEVERITY_WORDS = ("how severe", "severity of this", "explain severity", "why is this severe", "why is this critical", "why is this high risk")
OWASP_WORDS = ("owasp",)
CERT_WORDS = ("cert c", "cert-c", "cert rule", "sei cert")
MITRE_WORDS = ("mitre",)
CAPEC_WORDS = ("capec", "attack pattern")
PREDICTION_WORDS = ("explain the prediction", "explain prediction", "explain the verdict", "why is this vulnerable", "why was this flagged", "explain every vulnerability", "explain all vulnerabilities")
GENERAL_SCAN_WORDS = ("this function", "this code", "this scan", "flagged", "why is this", "explain this")

# Phase 3 additions: safer-API suggestions, an "optimized" (still security-rule-based,
# not a performance profiler -- see _generate_optimized) rewrite, and two reading
# levels for the same underlying explanation.
SAFER_API_WORDS = ("safer api", "safer function", "suggest safer", "safe alternative", "safer alternative", "recommend an api", "which api should i use")
OPTIMIZE_WORDS = ("optimized version", "optimize this", "generate optimized", "optimise this", "generate an optimized")
BEGINNER_WORDS = ("beginner explanation", "explain simply", "eli5", "simple explanation", "explain like i'm new", "explain like a beginner", "explain for a beginner")
EXPERT_WORDS = ("expert explanation", "technical explanation", "detailed explanation", "advanced explanation", "expert mode")

# C's nearest idiomatic equivalent to a "safer API" for each dangerous call.
SAFER_API_MAP = {
    "strcpy": "strncpy() (bounded, still needs manual NUL-termination) or strlcpy() where available",
    "strcat": "strncat() (bounded) or strlcat() where available",
    "gets": "fgets(buf, sizeof(buf), stdin) -- gets() has no bounded form and was removed from C11",
    "sprintf": "snprintf() -- takes an explicit buffer size",
    "vsprintf": "vsnprintf() -- takes an explicit buffer size",
    "scanf": "fgets() + sscanf() on the resulting bounded buffer, or scanf(\"%99s\", ...) with an explicit width",
    "system": "execvp()/execve() with an explicit argv array -- avoids shell interpretation entirely",
    "popen": "posix_spawn() or fork()+exec*() with an explicit argv array",
    "alloca": "a bounds-checked heap allocation (malloc + explicit size check) for anything sized from external input",
    "memcpy": "memcpy() is fine IF the length is clamped to the destination size first -- check the length, don't replace the call",
    "rand": "arc4random() (BSD/macOS) or a CSPRNG (e.g. getrandom() on Linux) if the value is security-sensitive; rand() is fine for non-security randomness",
}


def _branch_of(feature_name: str) -> str:
    if feature_name.startswith("embed_"):
        return "codebert"
    return "ast" if feature_name in ml_bridge.AST_FEATURE_COLS else "metrics"


def _get_record(db, scan_id):
    from database import ScanRecord
    return db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()


def _dangerous_api_explanation(api: str) -> str:
    sev, cwe, desc = code_intelligence.DANGEROUS_APIS.get(api, (0, None, None))
    parts = [f"`{api}()`"]
    if desc:
        parts.append(f"is flagged because: {desc}.")
    else:
        parts.append("is a commonly misused C standard library function.")
    if cwe:
        entry = knowledge_base.lookup(cwe)
        parts.append(
            f"\n\nThis maps to **{cwe} -- {entry['name']}** ({entry['severity']} severity"
            + (f", CVSS {entry['cvss']['score']}" if entry.get("cvss", {}).get("score") else "")
            + f").\n\n{entry['description']}\n\n**Mitigation:** {entry['mitigation'][0]}"
        )
    return " ".join(parts[:2]) + ("".join(parts[2:]) if len(parts) > 2 else "")


def _cwe_explanation(cwe_id: str) -> str:
    entry = knowledge_base.lookup(cwe_id)
    lines = [
        f"**{entry['id']} -- {entry['name']}** ({entry.get('aka', '')})",
        f"Severity: {entry['severity']}" + (f" | CVSS {entry['cvss']['score']}" if entry.get("cvss", {}).get("score") else ""),
        "",
        entry["description"],
        "",
        f"**Impact:** {entry['impact']}",
        "",
        "**Mitigation:**",
    ] + [f"- {m}" for m in entry["mitigation"]]
    return "\n".join(lines)


def _owasp_explanation(cwe_id: str) -> str:
    entry = knowledge_base.lookup(cwe_id)
    return (
        f"**OWASP mapping for {entry['id']} -- {entry['name']}**\n\n"
        f"OWASP reference: {entry['owasp_url']}\n\n"
        f"This weakness class is commonly grouped under OWASP's memory-safety / injection guidance "
        f"depending on context (e.g. buffer and format-string issues fall under OWASP's C/C++ memory-safety "
        f"guidance; command injection falls under OWASP Top 10 *Injection*)."
    )


def _cert_c_explanation(cwe_id: str) -> str:
    entry = knowledge_base.lookup(cwe_id)
    cert = entry.get("cert_c")
    if not cert:
        return (
            f"There isn't a single specific SEI CERT C rule catalogued here for {entry['id']}. "
            f"See the full SEI CERT C Coding Standard: {knowledge_base.CERT_C_CATALOG_URL}"
        )
    return (
        f"**SEI CERT C rule for {entry['id']} -- {entry['name']}**\n\n"
        f"**{cert['id']}** -- {cert['title']}\n\n"
        f"Full standard: {knowledge_base.CERT_C_CATALOG_URL}"
    )


def _mitre_explanation(cwe_id: str) -> str:
    entry = knowledge_base.lookup(cwe_id)
    return f"**MITRE CWE reference for {entry['id']}**\n\n{entry['mitre_url']}"


def _capec_explanation(cwe_id: str) -> str:
    entry = knowledge_base.lookup(cwe_id)
    capec = entry.get("capec")
    if not capec:
        return (
            f"No specific CAPEC attack pattern is catalogued here for {entry['id']}. "
            f"Browse the full CAPEC database: {knowledge_base.CAPEC_CATALOG_URL}"
        )
    return (
        f"**CAPEC attack pattern for {entry['id']} -- {entry['name']}**\n\n"
        f"**{capec['id']}** -- {capec['name']}\n\n"
        f"Catalog: https://capec.mitre.org/data/definitions/{capec['id'].split('-')[1]}.html"
    )


def _resolve_cwe_from_question(ql: str) -> str | None:
    m = CWE_RE.search(ql)
    if m:
        cwe_id = f"CWE-{m.group(1)}"
        if cwe_id in knowledge_base.KNOWLEDGE_BASE:
            return cwe_id
    for alias, api in API_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", ql):
            _, cwe, _ = code_intelligence.DANGEROUS_APIS.get(api, (0, None, None))
            if cwe:
                return cwe
    for phrase, cwe_id in CONCEPT_TO_CWE.items():
        if phrase in ql:
            return cwe_id
    return None


def _explain_scan(db, scan_id: str, question: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."

    intel = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
    verdict_line = (
        f"This scan (`{record.filename}`) was classified **{record.verdict}** by {record.model_used} "
        f"with {record.confidence:.1f}% confidence ({record.risk_level})."
    )

    if "function" in question.lower() and intel.get("functions"):
        target = intel["functions"][0]
        for f in intel["functions"]:
            if f["name"].lower() in question.lower():
                target = f
                break
        return f"{verdict_line}\n\n**`{target['name']}()`:** {target['summary']}"

    if intel.get("dangerous_apis"):
        apis = ", ".join(f"`{d['api']}()`" for d in intel["dangerous_apis"])
        return f"{verdict_line}\n\nThe main driver is the use of {apis}, which are known-dangerous APIs (see the Knowledge Base for details on each)."

    return f"{verdict_line}\n\nNo specific dangerous API pattern was matched -- the verdict is primarily driven by CodeBERT's semantic embedding and structural (AST/metrics) features rather than one obvious API call."


def _explain_prediction(db, scan_id: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."
    intel = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
    lines = [
        f"**Verdict: {record.verdict}** ({record.risk_level}, {record.risk_tag})",
        f"Vulnerability probability: **{record.vuln_probability:.1f}%** | Confidence: **{record.confidence:.1f}%** | Model: {record.model_used}",
        "",
    ]
    if intel.get("dangerous_apis"):
        lines.append("**Every flagged vulnerability in this file:**")
        for d in intel["dangerous_apis"]:
            entry = knowledge_base.lookup(d["cwe"]) if d.get("cwe") else None
            cwe_txt = f" -> {d['cwe']} ({entry['name']})" if entry else ""
            lines.append(f"- Line {d['line']}: `{d['api']}()`{cwe_txt}, {d['count']} occurrence(s)")
    else:
        lines.append("No specific dangerous-API pattern was matched in this file; the verdict comes primarily from CodeBERT's semantic embedding plus AST/metric structure rather than one identifiable API call.")
    scores = intel.get("scores", {}) if intel.get("available") else {}
    if scores:
        lines.append("")
        lines.append(f"Security score: {scores.get('security_score', '-')} / 100 | Quality: {scores.get('quality', '-')} / 100 | Maintainability Index: {scores.get('maintainability_index', '-')}")
    return "\n".join(lines)


def _explain_confidence(db, scan_id: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."
    conf = record.confidence or 0.0
    level = "high" if conf >= 75 else ("moderate" if conf >= 55 else "low")
    lines = [f"Confidence for this scan is **{conf:.1f}%**, which is **{level}**.", ""]
    if record.is_demo:
        lines.append("This scan ran in demo mode (trained model weights were unavailable at scan time), so confidence reflects a fallback heuristic rather than the trained ensemble.")
        return "\n".join(lines)
    try:
        d = {"ast_features": {}, "metric_features": {}}
        import json
        d["ast_features"] = json.loads(record.ast_features_json or "{}")
        d["metric_features"] = json.loads(record.metric_features_json or "{}")
        fv, _ = ml_bridge.full_feature_vector(record.code, d["ast_features"], d["metric_features"])
        model = ml_bridge.get_xgb_model()
        contributions = ml_bridge.approximate_contributions(model, fv, top_n=8) if model is not None else None
    except Exception:
        contributions = None

    if contributions:
        agreeing = sum(1 for c in contributions if (c["direction"] == "vulnerable") == (record.verdict == "VULNERABLE"))
        lines.append(
            f"Of the top {len(contributions)} contributing features, {agreeing} push toward the same verdict the model reached "
            f"({'VULNERABLE' if record.verdict == 'VULNERABLE' else 'NOT VULNERABLE'}) -- the more features agree, the higher the confidence."
        )
        lines.append("")
        lines.append("**Top contributing features:**")
        for c in contributions[:5]:
            branch = _branch_of(c["feature"])
            lines.append(f"- `{c['feature']}` ({branch}) -- z-score {c['z_score']:.2f}, pushing toward **{c['direction']}**")
    else:
        lines.append("A detailed per-feature contribution breakdown isn't available for this scan (feature baseline not computed), but confidence is derived from how far the model's predicted probability sits from the 50% decision boundary -- the further from 50%, the higher the confidence.")
    return "\n".join(lines)


def _explain_branch(db, scan_id: str, branch: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."
    names = {"ast": "AST (structural) branch", "metrics": "Software Metrics branch", "codebert": "CodeBERT (semantic embedding) branch"}
    label = names[branch]
    if record.is_demo:
        return f"This scan ran in demo mode, so a live {label} contribution breakdown isn't available."
    import json
    ast_feats = json.loads(record.ast_features_json or "{}")
    metric_feats = json.loads(record.metric_features_json or "{}")
    try:
        fv, _ = ml_bridge.full_feature_vector(record.code, ast_feats, metric_feats)
        model = ml_bridge.get_xgb_model()
        contributions = ml_bridge.approximate_contributions(model, fv, top_n=50) if model is not None else None
    except Exception:
        contributions = None

    if branch == "ast" and ast_feats:
        lines = [f"**{label}** contributed {len(ast_feats)} structural features for this file, including:"]
        for k, v in list(ast_feats.items())[:8]:
            lines.append(f"- `{k}` = {v}")
    elif branch == "metrics" and metric_feats:
        lines = [f"**{label}** contributed {len(metric_feats)} software-quality metrics for this file, including:"]
        for k, v in list(metric_feats.items())[:8]:
            lines.append(f"- `{k}` = {v}")
    else:
        lines = [f"**{label}** contributes a 768-dimensional semantic embedding of the code from CodeBERT -- it captures patterns and idioms learned from the training corpus rather than any single named feature."]

    if contributions:
        branch_contribs = [c for c in contributions if _branch_of(c["feature"]) == branch]
        if branch_contribs:
            lines.append("")
            lines.append(f"**Top {label} contributions for this specific prediction:**")
            for c in branch_contribs[:5]:
                lines.append(f"- `{c['feature']}` -- value {c['value']:.2f}, z-score {c['z_score']:.2f}, pushing toward **{c['direction']}**")
    return "\n".join(lines)


def _highlight_lines(db, scan_id: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."
    line_risks = ml_bridge.line_risk_scan(record.code)
    if not line_risks:
        return "No specific line-level risk was flagged in this file by the heuristic scanner."
    lines = [f"**{len(line_risks)} flagged line(s):**", ""]
    for lr in sorted(line_risks, key=lambda x: -x["severity"])[:15]:
        cwe = ", ".join(lr.get("cwe", [])) or "-"
        sev_label = ml_bridge.SEVERITY_LABELS.get(lr["severity"], "low")
        lines.append(f"- **Line {lr['line']}** ({sev_label}, {cwe}): {'; '.join(lr['reasons'])}")
    return "\n".join(lines)


def _suggest_fix(db, scan_id: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."
    rewrite = recommendations.suggest_secure_rewrite(record.code)
    if not rewrite["changed"]:
        return (
            "The automatic pattern-based rewriter didn't find a mechanical fix it's confident applying here "
            "(no known-dangerous-API pattern matched a rewrite rule). Open **Auto Patch Generator** for reference-card "
            "guidance, or **AI Recommendations** for the full best-practice checklist for this file."
        )
    lines = ["**Suggested secure rewrite** (rule-based, review before applying):", ""]
    for c in rewrite["changes"]:
        lines.append(f"- {c['description']} ({c['occurrences']} occurrence(s))")
    lines.append("")
    lines.append("Open **Auto Patch Generator** or **Code Diff Viewer** to see the full before/after side by side.")
    return "\n".join(lines)


def _suggest_safer_apis(db, scan_id: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."
    intel = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
    if not intel.get("dangerous_apis"):
        return "No dangerous API calls were identified in this file, so there's nothing to swap for a safer alternative."
    lines = ["**Safer API suggestions for this file:**", ""]
    for d in intel["dangerous_apis"]:
        alt = SAFER_API_MAP.get(d["api"])
        if alt:
            lines.append(f"- `{d['api']}()` (line {d['line']}) &rarr; {alt}")
        else:
            lines.append(f"- `{d['api']}()` (line {d['line']}) -- no single drop-in replacement; see the Knowledge Base entry for this call's mitigation guidance.")
    return "\n".join(lines)


def _generate_optimized(db, scan_id: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."
    rewrite = recommendations.suggest_secure_rewrite(record.code)
    header = (
        "Heads up: this pipeline has no runtime profiler, so \"optimized\" here means the same rule-based "
        "**security** rewrite used elsewhere (bounded, safe API calls) -- not a performance optimization. "
        "I'm not going to pretend to speed up code I can't actually benchmark.\n\n"
    )
    if not rewrite["changed"]:
        return header + "No mechanical rewrite rule matched this file, so there's no rewritten version to show."
    lines = [header + "**Rewrite applied:**", ""]
    for c in rewrite["changes"]:
        lines.append(f"- {c['description']} ({c['occurrences']} occurrence(s))")
    lines.append("\nOpen **Code Diff Viewer** to see the full before/after.")
    return "\n".join(lines)


def _beginner_explanation(db, scan_id: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."
    intel = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
    if record.verdict != "VULNERABLE":
        return (
            f"In plain terms: this file (`{record.filename}`) looks **safe**. The AI didn't spot any of the risky "
            f"patterns it was trained to recognise -- things like copying text into a box that's too small for it, "
            f"or using memory after throwing it away."
        )
    if intel.get("dangerous_apis"):
        top = intel["dangerous_apis"][0]
        entry = knowledge_base.lookup(top["cwe"]) if top.get("cwe") else None
        simple_name = entry["name"].lower() if entry else "a risky pattern"
        return (
            f"In plain terms: this file (`{record.filename}`) uses a function called `{top['api']}()` that doesn't check "
            f"how much data it's handling. Imagine pouring a liter of water into a cup that only holds 200ml -- the extra "
            f"water spills everywhere and makes a mess. That's roughly what happens in memory here: it's called "
            f"**{simple_name}**, and it can crash the program or, in the worst case, let an attacker sneak in their own instructions."
        )
    return (
        f"In plain terms: the AI flagged this file (`{record.filename}`) as risky based on its overall shape and structure, "
        f"not one single obvious mistake -- similar to how a doctor might say 'something looks off' from a scan before "
        f"pointing to one exact spot. Worth a closer manual look."
    )


def _expert_explanation(db, scan_id: str) -> str:
    # The existing prediction explanation is already written at the technical/expert
    # level (CWE ids, CVSS, contribution features) -- "expert mode" surfaces it directly.
    return _explain_prediction(db, scan_id)


def _explain_exploit(db, scan_id: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."
    intel = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
    if not intel.get("dangerous_apis"):
        return "No specific dangerous API was identified, so there's no concrete exploit primitive to describe for this file -- treat the AI verdict as a prompt for manual review rather than a proven exploit path."
    top = intel["dangerous_apis"][0]
    if not top.get("cwe"):
        return f"`{top['api']}()` at line {top['line']} was flagged, but it doesn't map to a catalogued CWE with exploit narrative here."
    entry = knowledge_base.lookup(top["cwe"])
    lines = [
        f"**Exploit scenario for `{top['api']}()` at line {top['line']} ({entry['id']} -- {entry['name']}):**",
        "",
        entry["impact"],
        "",
    ]
    if entry.get("real_attacks"):
        lines.append("**Real-world precedent:**")
        for ra in entry["real_attacks"]:
            lines.append(f"- {ra}")
        lines.append("")
    if entry.get("cvss", {}).get("score"):
        lines.append(f"CVSS baseline: {entry['cvss']['score']} ({entry['cvss']['vector']})")
    return "\n".join(lines).strip("\n")


def _explain_developer_mistake(db, scan_id: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."
    intel = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
    if not intel.get("dangerous_apis"):
        return "No single dangerous API call stands out as 'the mistake' here -- the model's verdict is driven by more diffuse structural/semantic signal, so a targeted code review is the right next step."
    lines = ["**What likely went wrong:**", ""]
    for d in intel["dangerous_apis"][:5]:
        desc = d.get("description") or "this call is commonly misused without proper bounds/validation."
        lines.append(f"- Line {d['line']}: using `{d['api']}()` -- {desc}")
    return "\n".join(lines)


def _explain_priority(db, scan_id: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."
    line_risks = ml_bridge.line_risk_scan(record.code)
    if not line_risks:
        return "Nothing was flagged at the line level, so there's no specific remediation order to give -- overall risk here comes from broader structural/semantic signal rather than one API call."
    ranked = sorted(line_risks, key=lambda x: -x["severity"])
    lines = ["**Suggested remediation order (most urgent first):**", ""]
    for i, lr in enumerate(ranked[:10], 1):
        cwe = ", ".join(lr.get("cwe", [])) or "-"
        sev_label = ml_bridge.SEVERITY_LABELS.get(lr["severity"], "low").upper()
        lines.append(f"{i}. Line {lr['line']} -- {sev_label} ({cwe}): {'; '.join(lr['reasons'])}")
    return "\n".join(lines)


def _explain_severity(db, scan_id: str) -> str:
    record = _get_record(db, scan_id)
    if not record:
        return "I couldn't find that scan -- it may have been deleted."
    intel = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
    lines = [f"This file is rated **{record.risk_level}** ({record.risk_tag})."]
    if intel.get("dangerous_apis"):
        worst = intel["dangerous_apis"][0]
        if worst.get("cwe"):
            entry = knowledge_base.lookup(worst["cwe"])
            lines.append(
                f"\nThe most severe finding is `{worst['api']}()` at line {worst['line']}, mapping to {entry['id']} "
                f"({entry['severity']} severity"
                + (f", CVSS {entry['cvss']['score']}" if entry.get("cvss", {}).get("score") else "")
                + f"). Severity here reflects both how easy the weakness class is to trigger and how much damage it "
                f"can cause if triggered (confidentiality/integrity/availability impact), not just the model's raw probability."
            )
    else:
        lines.append(f"\nSeverity here is derived from the model's overall vulnerability probability ({record.vuln_probability:.1f}%) since no single dangerous API dominates the signal.")
    return "\n".join(lines)


SUGGESTED_QUESTIONS = [
    "Why is strcpy dangerous?",
    "What is CWE-416?",
    "Explain the prediction",
    "Highlight vulnerable lines",
    "Suggest a fix",
    "Suggest safer APIs",
    "Explain exploit possibility",
    "What is the CERT C rule for this?",
    "What should I fix first?",
    "Give me a beginner explanation",
    "Give me an expert explanation",
]


def answer(question: str, scan_id: str = None, db=None) -> dict:
    q = (question or "").strip()
    ql = q.lower()

    if ql in GREETINGS:
        return {
            "answer": (
                "Hi! I'm the Security Copilot -- ask me about a dangerous API (e.g. \"Why is strcpy dangerous?\"), "
                "a CWE (e.g. \"What is CWE-416?\"), OWASP/CERT-C/MITRE/CAPEC mappings, or, if you have a scan open, "
                "\"Explain the prediction\", \"Highlight vulnerable lines\", \"Suggest a fix\", \"Explain exploit possibility\", "
                "\"Why is confidence high?\", or \"What should I fix first?\"."
            ),
            "sources": [], "suggested": SUGGESTED_QUESTIONS,
        }

    # Reference-lookup intents (OWASP / CERT-C / MITRE / CAPEC) -- resolve a
    # CWE from the question (explicit id, API name, or concept phrase) first.
    if any(w in ql for w in OWASP_WORDS) or any(w in ql for w in CERT_WORDS) or any(w in ql for w in MITRE_WORDS) or any(w in ql for w in CAPEC_WORDS):
        cwe_id = _resolve_cwe_from_question(ql)
        if not cwe_id and scan_id and db is not None:
            record = _get_record(db, scan_id)
            if record:
                intel = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
                if intel.get("dangerous_apis") and intel["dangerous_apis"][0].get("cwe"):
                    cwe_id = intel["dangerous_apis"][0]["cwe"]
        if cwe_id:
            if any(w in ql for w in CERT_WORDS):
                return {"answer": _cert_c_explanation(cwe_id), "sources": [cwe_id], "suggested": SUGGESTED_QUESTIONS}
            if any(w in ql for w in MITRE_WORDS):
                return {"answer": _mitre_explanation(cwe_id), "sources": [cwe_id], "suggested": SUGGESTED_QUESTIONS}
            if any(w in ql for w in CAPEC_WORDS):
                return {"answer": _capec_explanation(cwe_id), "sources": [cwe_id], "suggested": SUGGESTED_QUESTIONS}
            if any(w in ql for w in OWASP_WORDS):
                return {"answer": _owasp_explanation(cwe_id), "sources": [cwe_id], "suggested": SUGGESTED_QUESTIONS}

    # Scan-aware intents (require an open scan).
    if scan_id and db is not None:
        if any(w in ql for w in LINE_WORDS):
            return {"answer": _highlight_lines(db, scan_id), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in SAFER_API_WORDS):
            return {"answer": _suggest_safer_apis(db, scan_id), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in OPTIMIZE_WORDS):
            return {"answer": _generate_optimized(db, scan_id), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in BEGINNER_WORDS):
            return {"answer": _beginner_explanation(db, scan_id), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in EXPERT_WORDS):
            return {"answer": _expert_explanation(db, scan_id), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in FIX_WORDS):
            return {"answer": _suggest_fix(db, scan_id), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in CONFIDENCE_WORDS):
            return {"answer": _explain_confidence(db, scan_id), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in CODEBERT_WORDS):
            return {"answer": _explain_branch(db, scan_id, "codebert"), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in METRICS_WORDS):
            return {"answer": _explain_branch(db, scan_id, "metrics"), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in AST_WORDS):
            return {"answer": _explain_branch(db, scan_id, "ast"), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in EXPLOIT_WORDS):
            return {"answer": _explain_exploit(db, scan_id), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in MISTAKE_WORDS):
            return {"answer": _explain_developer_mistake(db, scan_id), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in PRIORITY_WORDS):
            return {"answer": _explain_priority(db, scan_id), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in SEVERITY_WORDS):
            return {"answer": _explain_severity(db, scan_id), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}
        if any(w in ql for w in PREDICTION_WORDS):
            return {"answer": _explain_prediction(db, scan_id), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}

    # 1. Explicit CWE id
    m = CWE_RE.search(ql)
    if m:
        cwe_id = f"CWE-{m.group(1)}"
        if cwe_id in knowledge_base.KNOWLEDGE_BASE:
            return {"answer": _cwe_explanation(cwe_id), "sources": [cwe_id], "suggested": SUGGESTED_QUESTIONS}

    # 2. Named dangerous API
    for alias, api in API_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", ql):
            return {"answer": _dangerous_api_explanation(api), "sources": [api], "suggested": SUGGESTED_QUESTIONS}

    # 3. Vulnerability-class concept
    for phrase, cwe_id in CONCEPT_TO_CWE.items():
        if phrase in ql:
            return {"answer": _cwe_explanation(cwe_id), "sources": [cwe_id], "suggested": SUGGESTED_QUESTIONS}

    # 4. Generic scan-specific question
    if scan_id and db is not None and any(w in ql for w in GENERAL_SCAN_WORDS):
        return {"answer": _explain_scan(db, scan_id, ql), "sources": [scan_id], "suggested": SUGGESTED_QUESTIONS}

    # 5. Fallback
    return {
        "answer": (
            "I don't have a deterministic answer for that yet -- I can currently explain dangerous C APIs "
            "(strcpy, gets, sprintf, malloc, free, ...), CWE categories (e.g. \"CWE-120\" or \"buffer overflow\"), "
            "OWASP/CERT-C/MITRE/CAPEC mappings, and -- if you navigate here from a scan -- that scan's prediction, "
            "confidence, AST/Metrics/CodeBERT contributions, flagged lines, suggested fixes, exploit scenario, and "
            "remediation priority. Try one of the suggested questions below."
        ),
        "sources": [], "suggested": SUGGESTED_QUESTIONS,
    }
