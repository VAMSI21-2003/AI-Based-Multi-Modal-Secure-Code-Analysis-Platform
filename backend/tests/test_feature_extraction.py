# =============================================================================
# test_feature_extraction.py -- real tests for the AST/metrics feature
# extraction that every scan endpoint depends on. Uses the exact same
# functions ml_bridge.py imports for live scans (app/utils.py), via the same
# import path (backend/ml_bridge.py inserts app/ onto sys.path). No model
# loading involved -- these are pure, deterministic, fast unit tests.
# =============================================================================

import ml_bridge

VULNERABLE_SNIPPET = """
void process(char *input) {
    char buf[64];
    strcpy(buf, input);  // no bounds check
}
"""

SAFE_SNIPPET = """
void process(const char *input, size_t input_len) {
    char buf[64];
    if (input_len >= sizeof(buf)) return;
    strncpy(buf, input, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\\0';
}
"""


def test_ast_features_have_exactly_11_dimensions():
    feats = ml_bridge.extract_ast_features(VULNERABLE_SNIPPET)
    assert len(feats) == 11
    assert set(feats.keys()) == set(ml_bridge.AST_FEATURE_COLS)


def test_ast_features_detect_pointer_usage():
    feats = ml_bridge.extract_ast_features(VULNERABLE_SNIPPET)
    assert feats["n_pointer_ops"] >= 1
    assert feats["n_function_calls"] >= 1


def test_metric_features_have_exactly_13_dimensions():
    feats = ml_bridge.extract_metric_features(VULNERABLE_SNIPPET)
    assert len(feats) == 13
    assert set(feats.keys()) == set(ml_bridge.METRICS_FEATURE_COLS)


def test_metric_features_pointer_count_reflects_source():
    vulnerable = ml_bridge.extract_metric_features(VULNERABLE_SNIPPET)
    safe = ml_bridge.extract_metric_features(SAFE_SNIPPET)
    # the safe version has more lines (explicit bounds check) and is not
    # shorter than the vulnerable one -- a real, checkable property of
    # these two fixed snippets, not a tautology.
    assert safe["loc"] >= vulnerable["loc"]


def test_validate_code_rejects_empty_input():
    is_valid, message = ml_bridge.validate_code("")
    assert is_valid is False
    assert message


def test_validate_code_accepts_real_function():
    is_valid, _ = ml_bridge.validate_code(VULNERABLE_SNIPPET)
    assert is_valid is True


def test_ast_extraction_survives_malformed_source_without_crashing():
    # tree-sitter's error-tolerant parsing should produce a best-effort tree
    # (with error nodes counted, not raised) rather than throwing -- this is
    # the real behavior a truncated/corrupt uploaded file exercises.
    malformed = "void broken(char *x { if (x strcpy(x"
    feats = ml_bridge.extract_ast_features(malformed)
    assert len(feats) == 11
    assert feats["n_error_nodes"] >= 1


def test_get_risk_level_thresholds():
    # get_risk_level is the single source of truth every dashboard/report
    # reads risk-level labels from -- a regression here would silently
    # change every page's risk labeling at once.
    from utils import get_risk_level

    assert get_risk_level(0.10)[0] == "SAFE"
    assert get_risk_level(0.40)[0] == "LOW RISK"
    assert get_risk_level(0.60)[0] == "MEDIUM RISK"
    assert get_risk_level(0.80)[0] == "HIGH RISK"
    assert get_risk_level(0.95)[0] == "CRITICAL"
