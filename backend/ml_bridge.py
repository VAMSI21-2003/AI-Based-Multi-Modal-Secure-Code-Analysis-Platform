# =============================================================================
# ml_bridge.py
# Bridges the FastAPI backend to the EXISTING, already-trained ML pipeline.
#
# IMPORTANT: This file does NOT retrain or modify any model. It only imports
# and reuses the functions already defined in app/predictor.py and
# app/utils.py (built during the original CodeBERT + AST + Metrics + XGBoost
# project). New code here is limited to:
#   - loading/caching the existing models
#   - deriving presentation-layer artifacts from an existing prediction
#     (AST tree for visualisation, per-line heuristic risk highlighting,
#      approximate feature contributions, PCA projection of embeddings)
# =============================================================================

import os
import sys
import re
import json
import time
import functools
from typing import Optional

import system_monitor
import code_intelligence

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(PROJECT_ROOT, "app")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
BACKEND_DATA_DIR = os.path.join(PROJECT_ROOT, "backend", "data")

if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from utils import (          # noqa: E402
    extract_ast_features,
    extract_metric_features,
    build_feature_vector,
    get_verdict,
    validate_code,
    describe_features,
    AST_FEATURE_COLS,
    METRICS_FEATURE_COLS,
)
from predictor import (      # noqa: E402
    load_xgboost_model,
    load_rf_model,
    load_codebert_components,
    extract_codebert_embedding,
    predict_with_model,
    predict_functions_with_model,
    demo_predict,
    XGB_MODEL_PATH,
    RF_MODEL_PATH,
)


# ── Cached model/tokenizer singletons (loaded once per process) ─────────────

@functools.lru_cache(maxsize=1)
def get_xgb_model():
    return system_monitor.timed_model_load("xgboost", load_xgboost_model)


@functools.lru_cache(maxsize=1)
def get_rf_model():
    return system_monitor.timed_model_load("random_forest", load_rf_model)


@functools.lru_cache(maxsize=1)
def get_codebert():
    tokenizer, model = system_monitor.timed_model_load("codebert", load_codebert_components)
    system_monitor.record_codebert_available(tokenizer is not None and model is not None)
    return tokenizer, model


def models_status() -> dict:
    return {
        "xgboost": {
            "available": os.path.exists(XGB_MODEL_PATH),
            "path": XGB_MODEL_PATH,
        },
        "random_forest": {
            "available": os.path.exists(RF_MODEL_PATH),
            "path": RF_MODEL_PATH,
        },
    }


def run_prediction(code: str, model_choice: str = "XGBoost") -> dict:
    """
    Runs the trained pipeline: AST + Metrics + CodeBERT -> 792-dim vector ->
    trained classifier. Falls back to the heuristic demo predictor if no
    trained model exists.

    Per-function inference (docs/PER_FUNCTION_INFERENCE_DESIGN.md): `code`
    is split into its individual functions first (same tree-sitter grammar
    code_intelligence.py already uses elsewhere), and the pipeline above
    runs independently per function -- matching the granularity the model
    was actually trained on (Devign rows are individual functions), instead
    of the whole file, which was silently truncating most real files'
    CodeBERT input to their first ~15% (measured: 80% of real files exceed
    512 tokens, vs. 45.5% for individual functions). The file-level verdict
    returned is the WORST function's result (max vuln_probability) -- the
    same "escalate to the worst signal, never suppress" principle already
    used by evidence_based_risk() below, not a new scheme. Files with no
    detected functions (headers, unparseable code) fall back to the
    original whole-code path unchanged.
    """
    _t0 = time.time()

    xgb_model = get_xgb_model()
    rf_model = get_rf_model()

    if model_choice == "XGBoost" and xgb_model is not None:
        active_model, active_name = xgb_model, "XGBoost"
    elif model_choice == "Random Forest" and rf_model is not None:
        active_model, active_name = rf_model, "Random Forest"
    elif xgb_model is not None:
        active_model, active_name = xgb_model, "XGBoost (fallback)"
    elif rf_model is not None:
        active_model, active_name = rf_model, "Random Forest (fallback)"
    else:
        active_model, active_name = None, None

    if active_model is not None:
        tokenizer, codebert_model = get_codebert()
        result = _predict_per_function_or_whole(code, active_model, active_name, tokenizer, codebert_model)
        result["is_demo"] = False
    else:
        result = demo_predict(code)

    result["insights"] = describe_features(
        result.get("ast_features", {}), result.get("metric_features", {})
    )
    system_monitor.record_prediction_latency(time.time() - _t0)
    return result


def _predict_per_function_or_whole(code: str, model, model_name: str, tokenizer, codebert_model) -> dict:
    functions = code_intelligence.extract_functions(code)
    if not functions:
        # No function_definition nodes found (header, unparseable code, or
        # tree-sitter unavailable) -- unchanged whole-code behavior.
        result = predict_with_model(code, model, model_name, tokenizer, codebert_model)
        result["function_results"] = None
        result["functions_analyzed"] = 0
        return result

    function_results = predict_functions_with_model(functions, model, model_name, tokenizer, codebert_model)

    # Max risk wins -- never averaged, never top-N. See the run_prediction
    # docstring above and docs/PER_FUNCTION_INFERENCE_DESIGN.md Section 3.
    worst = max(function_results, key=lambda r: r["vuln_probability"])
    result = dict(worst)
    result["embedding_source"] = (
        f"CodeBERT (microsoft/codebert-base), batched per-function over {len(function_results)} function(s)"
    )
    result["feature_vector_shape"] = (len(function_results), 792)
    result["function_results"] = function_results
    result["functions_analyzed"] = len(function_results)
    return result


# =============================================================================
# DERIVED ARTIFACT 1: AST tree (for the AST Tree Viewer visualisation)
# =============================================================================

def get_ast_tree(code: str, max_nodes: int = 600) -> dict:
    """
    Parses code with the same tree-sitter grammar used for feature extraction
    and returns a nested JSON tree (not just counts) so the UI can render an
    interactive AST viewer. Purely a visualisation aid -- does not feed the model.
    """
    try:
        import tree_sitter_c as tsc
        from tree_sitter import Language, Parser

        c_language = Language(tsc.language())
        parser = Parser(c_language)
        tree = parser.parse(bytes(code, "utf-8"))
        root = tree.root_node

        counter = {"n": 0}

        def to_dict(node, depth=0):
            counter["n"] += 1
            if counter["n"] > max_nodes or depth > 40:
                return None
            children = []
            for child in node.children:
                cd = to_dict(child, depth + 1)
                if cd is not None:
                    children.append(cd)
            text = ""
            if not children:
                try:
                    text = node.text.decode("utf-8", errors="replace")[:40]
                except Exception:
                    text = ""
            return {
                "type": node.type,
                "start": node.start_point[0] + 1,
                "end": node.end_point[0] + 1,
                "text": text,
                "children": children,
                "isError": node.type == "ERROR",
            }

        return {"available": True, "tree": to_dict(root)}
    except Exception as e:
        return {"available": False, "error": str(e), "tree": None}


# =============================================================================
# DERIVED ARTIFACT 2: line-level heuristic risk scoring (for the heatmap)
# =============================================================================
#
# This is a transparent, rule-based pattern scanner over the raw source text.
# It is intentionally separate from the trained classifier: the classifier
# gives one function-level verdict, this gives line-level annotations so the
# UI can highlight *which* lines likely drove that verdict. Patterns chosen
# reflect classic CWE categories (buffer overflow, format string, integer
# overflow, null deref, use-after-free, race, etc).

DANGEROUS_PATTERNS = [
    # (regex, severity 1-4, short reason, cwe)
    (r"\bstrcpy\s*\(", 4, "strcpy() has no bounds checking", "CWE-120"),
    (r"\bstrcat\s*\(", 4, "strcat() has no bounds checking", "CWE-120"),
    (r"\bgets\s*\(", 4, "gets() cannot limit input length -- always unsafe", "CWE-242"),
    (r"\bsprintf\s*\(", 3, "sprintf() can overflow the destination buffer", "CWE-120"),
    (r"\bscanf\s*\(\s*\"[^\"]*%s", 3, "%s in scanf() has no width limit", "CWE-120"),
    (r"(?<![sfv])\bprintf\s*\(\s*\w+\s*[,)]", 4, "format string is a variable, not a literal -- format string vulnerability", "CWE-134"),
    (r"\bfprintf\s*\(\s*\w+\s*,\s*\w+\s*[,)]", 4, "format string is a variable, not a literal -- format string vulnerability", "CWE-134"),
    (r"\bvsprintf\s*\(", 3, "vsprintf() can overflow the destination buffer", "CWE-120"),
    (r"\bmemcpy\s*\(", 2, "memcpy() length should be verified against destination size", "CWE-120"),
    (r"\bmemmove\s*\(", 2, "memmove() length should be verified against destination size", "CWE-120"),
    (r"\balloca\s*\(", 3, "alloca() can overflow the stack with attacker-controlled size", "CWE-770"),
    (r"\bmalloc\s*\([^)]*\*[^)]*\)", 3, "multiplication inside malloc() may overflow", "CWE-190"),
    (r"\bfree\s*\(\s*(\w+)\s*\)(?![^;]*\1\s*=\s*NULL)", 2, "pointer freed without being reset to NULL (possible use-after-free / double-free)", "CWE-416"),
    (r"%n", 4, "%n format specifier can write to memory -- format string vulnerability", "CWE-134"),
    (r"\bsystem\s*\(", 3, "system() with unsanitised input enables command injection", "CWE-78"),
    (r"\bexec[lv]p?e?\s*\(", 2, "exec family call -- verify all arguments are sanitised", "CWE-78"),
    (r"\bstrncpy\s*\([^,]+,[^,]+,\s*sizeof\s*\([^)]+\)\s*\)(?!\s*;\s*\w+\[)", 1, "strncpy() may not NUL-terminate if source >= size", "CWE-170"),
    (r"\[\s*\w+\s*\+\+\s*\]|\[\s*\+\+\s*\w+\s*\]", 1, "pointer/index increment inside subscript -- verify bounds", "CWE-125"),
    (r"==\s*NULL\s*\)\s*;", 2, "empty statement after NULL check -- guard body may be missing", "CWE-476"),
]

MALLOC_FAMILY = re.compile(r"\b(malloc|calloc|realloc)\s*\(")
NULLCHECK_NEARBY = re.compile(r"==\s*NULL|!=\s*NULL|if\s*\(\s*!\s*\w+\s*\)")

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_PREPROC_DIAGNOSTIC_RE = re.compile(r"^[ \t]*#[ \t]*(warning|error)\b.*$", re.MULTILINE)


def _blank_non_code_text(code: str) -> str:
    """
    Blank out (never delete -- line numbers must stay aligned with the
    original source) block comments, line comments, and #warning/#error
    preprocessor diagnostics before the regex heuristic scan below runs.
    Without this, a comment or compiler warning that merely MENTIONS a
    dangerous function name -- e.g. zlib's gzwrite.c:
        #warning "you can recompile with ZLIB_INSECURE to use vsprintf()"
        /* prevent use of insecure vsprintf(), unless purposefully requested */
    or libpng's example.c:
        * If you allocated it with malloc() instead of png_malloc(), use free()
    -- gets flagged as if it were an actual call. Confirmed as a real,
    repeated false positive against real repositories during Phase 5.3
    validation. The AST-based dangerous-API list (code_intelligence.py)
    is unaffected -- tree-sitter already distinguishes comments from code
    at the syntax level; this only patches the separate regex heuristic.
    """
    def _blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    code = _BLOCK_COMMENT_RE.sub(_blank, code)
    code = _LINE_COMMENT_RE.sub(_blank, code)
    code = _PREPROC_DIAGNOSTIC_RE.sub(_blank, code)
    return code


def line_risk_scan(code: str) -> list:
    """
    Returns a list of {line, severity(0-4), reasons: [...], cwe: [...]} for
    every line that matches a known-dangerous pattern. severity 0 = clean.
    Matching runs against a comment/preprocessor-diagnostic-blanked copy of
    the source (see _blank_non_code_text); the "code" field returned to the
    caller still shows the real, unmodified source line.
    """
    original_lines = code.split("\n")
    scan_lines = _blank_non_code_text(code).split("\n")
    results = []

    # Track malloc-family calls without a NULL check within the next 2 lines.
    for idx, scan_line in enumerate(scan_lines):
        line_no = idx + 1
        severity = 0
        reasons = []
        cwes = []

        for pattern, sev, reason, cwe in DANGEROUS_PATTERNS:
            if re.search(pattern, scan_line):
                severity = max(severity, sev)
                reasons.append(reason)
                cwes.append(cwe)

        if MALLOC_FAMILY.search(scan_line):
            lookahead = "\n".join(scan_lines[idx: idx + 3])
            if not NULLCHECK_NEARBY.search(lookahead):
                severity = max(severity, 2)
                reasons.append("allocation result does not appear to be NULL-checked nearby")
                cwes.append("CWE-476")

        if severity > 0:
            results.append({
                "line": line_no,
                "code": original_lines[idx],
                "severity": severity,
                "reasons": reasons,
                "cwe": sorted(set(cwes)),
            })

    return results


SEVERITY_LABELS = {0: "clean", 1: "low", 2: "medium", 3: "high", 4: "critical"}

# Same 5-level scale the trained model's own get_risk_level() already uses
# (app/utils.py) -- reused here only as a shared vocabulary for display,
# never imported from or written back into that file.
RISK_LEVELS = ["SAFE", "LOW RISK", "MEDIUM RISK", "HIGH RISK", "CRITICAL"]
_SEVERITY_TO_LEVEL = {0: "SAFE", 1: "LOW RISK", 2: "MEDIUM RISK", 3: "HIGH RISK", 4: "CRITICAL"}


def evidence_based_risk(ml_risk_level: str, line_risks: list) -> dict:
    """
    Additive, display-only cross-check between the trained model's verdict
    and the deterministic evidence already computed elsewhere (line_risk_scan
    above). Does NOT alter, override, or feed back into the ML prediction --
    it only decides what to SHOW alongside it, so a case like "ML says
    MEDIUM RISK but the code contains gets()/strcpy() (severity 4)" is never
    displayed as if the two disagreed. The combined level is always the
    WORSE of the two -- deterministic evidence can escalate the displayed
    risk, never suppress or downgrade the model's own signal.
    """
    max_severity = max((r["severity"] for r in line_risks), default=0)
    evidence_level = _SEVERITY_TO_LEVEL[max_severity]

    ml_rank = RISK_LEVELS.index(ml_risk_level) if ml_risk_level in RISK_LEVELS else 0
    evidence_rank = RISK_LEVELS.index(evidence_level)
    combined_rank = max(ml_rank, evidence_rank)

    top_reasons = []
    if max_severity > 0:
        seen = set()
        for r in line_risks:
            if r["severity"] != max_severity:
                continue
            for reason, cwe in zip(r["reasons"], r["cwe"] or [None] * len(r["reasons"])):
                key = (reason, cwe)
                if key in seen:
                    continue
                seen.add(key)
                top_reasons.append({"line": r["line"], "reason": reason, "cwe": cwe})
            if len(top_reasons) >= 5:
                break

    return {
        "level": RISK_LEVELS[combined_rank],
        "ml_level": ml_risk_level,
        "evidence_level": evidence_level,
        "escalated": combined_rank > ml_rank,
        "max_finding_severity": max_severity,
        "reasons": top_reasons,
    }


# =============================================================================
# DERIVED ARTIFACT 3: approximate per-sample feature contribution
# =============================================================================
#
# We do NOT add a SHAP dependency (keeps the environment untouched). Instead
# we compute a transparent, documented approximation:
#     contribution_i = global_feature_importance_i * z_score(value_i)
# i.e. "how important is this feature globally, times how unusual is this
# sample's value for that feature". This is clearly labelled as an
# approximation in the API response, not a SHAP value.

@functools.lru_cache(maxsize=1)
def _feature_baseline():
    """
    Dataset mean/std per feature column, used only to compute the
    approximate contribution above. Falls back to None if the fused
    feature file is not available (contribution panel is then omitted).
    """
    path = os.path.join(PROJECT_ROOT, "dataset", "processed", "final_features.csv")
    if not os.path.exists(path):
        return None
    try:
        import pandas as pd
        df = pd.read_csv(path, nrows=5000)  # sample is enough for mean/std
        feat_cols = AST_FEATURE_COLS + METRICS_FEATURE_COLS + [f"embed_{i:03d}" for i in range(768)]
        feat_cols = [c for c in feat_cols if c in df.columns]
        mean = df[feat_cols].mean().values
        std = df[feat_cols].std().replace(0, 1).values
        return {"cols": feat_cols, "mean": mean, "std": std}
    except Exception:
        return None


def approximate_contributions(model, feature_vector: np.ndarray, top_n: int = 15) -> Optional[list]:
    baseline = _feature_baseline()
    if baseline is None:
        return None
    try:
        importances = getattr(model, "feature_importances_", None)
        if importances is None:
            return None
        cols = baseline["cols"]
        mean = baseline["mean"]
        std = baseline["std"]
        n = min(len(cols), len(importances), len(feature_vector))
        z = (feature_vector[:n] - mean[:n]) / std[:n]
        contrib = importances[:n] * z
        order = np.argsort(-np.abs(contrib))[:top_n]
        out = []
        for i in order:
            out.append({
                "feature": cols[i],
                "value": float(feature_vector[i]),
                "importance": float(importances[i]),
                "z_score": float(z[i]),
                "contribution": float(contrib[i]),
                "direction": "vulnerable" if contrib[i] > 0 else "safe",
            })
        return out
    except Exception:
        return None


# =============================================================================
# DERIVED ARTIFACT 4: embedding PCA projection (precomputed offline)
# =============================================================================

_PCA_BG_PATH = os.path.join(BACKEND_DATA_DIR, "pca_background.json")
_PCA_MODEL_PATH = os.path.join(BACKEND_DATA_DIR, "pca_model.npz")


@functools.lru_cache(maxsize=1)
def _pca_components():
    if not os.path.exists(_PCA_MODEL_PATH):
        return None
    data = np.load(_PCA_MODEL_PATH)
    return {"mean": data["mean"], "components": data["components"]}


@functools.lru_cache(maxsize=1)
def pca_background() -> Optional[dict]:
    if not os.path.exists(_PCA_BG_PATH):
        return None
    with open(_PCA_BG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def project_embedding(embedding: np.ndarray) -> Optional[list]:
    comp = _pca_components()
    if comp is None:
        return None
    centered = embedding - comp["mean"]
    coords = centered @ comp["components"].T
    return [float(coords[0]), float(coords[1])]


# =============================================================================
# Feature vector helper (kept here so routers don't reach into utils directly)
# =============================================================================

def full_feature_vector(code: str, ast_feats: dict, metric_feats: dict) -> np.ndarray:
    tokenizer, codebert_model = get_codebert()
    if tokenizer is not None and codebert_model is not None:
        embedding = extract_codebert_embedding(code, tokenizer, codebert_model)
    else:
        embedding = np.zeros(768, dtype=np.float64)
    return build_feature_vector(ast_feats, metric_feats, embedding), embedding
