# =============================================================================
# test_ml_pipeline.py -- real tests for the fusion/inference pipeline's
# determinism and shape guarantees, and for input validation at the API
# boundary (Phase 3: testing foundation). These exercise the actual trained
# model artifacts and the actual CodeBERT tokenizer/model -- not mocks -- so
# they are slower than test_feature_extraction.py, but they verify real
# behavior: that inference is deterministic (no hidden randomness at predict
# time) and that the fused feature vector has exactly the shape training
# assumed (11 AST + 13 metrics + 768 CodeBERT = 792).
# =============================================================================

import numpy as np
from fastapi.testclient import TestClient

import ml_bridge
import github_service
from main import app

client = TestClient(app)

VULNERABLE_SNIPPET = """
void copy_input(char *dest, const char *src) {
    strcpy(dest, src);
}
"""


def test_prediction_is_deterministic_for_the_same_input():
    # Neither XGBoost's nor Random Forest's predict() has any randomness at
    # inference time (only training does) -- running the exact same code
    # through the exact same model twice must yield the exact same
    # probability, not just the same verdict. A regression here would mean
    # something non-deterministic (e.g. an uninitialized buffer, a
    # thread-unsafe cache) crept into the inference path.
    first = ml_bridge.run_prediction(VULNERABLE_SNIPPET, "XGBoost")
    second = ml_bridge.run_prediction(VULNERABLE_SNIPPET, "XGBoost")
    assert first["vuln_probability"] == second["vuln_probability"]
    assert first["verdict"] == second["verdict"]
    assert first["risk_level"] == second["risk_level"]


def test_fusion_vector_has_exactly_792_dimensions_in_the_trained_order():
    # Guards the single most fragile invariant in this pipeline: the fused
    # vector's dimension order (11 AST | 13 metrics | 768 CodeBERT) must
    # match what src/model/train_classifier.py actually trained on, or every
    # prediction becomes silently meaningless despite running without error.
    ast_feats = ml_bridge.extract_ast_features(VULNERABLE_SNIPPET)
    metric_feats = ml_bridge.extract_metric_features(VULNERABLE_SNIPPET)
    vector, embedding = ml_bridge.full_feature_vector(VULNERABLE_SNIPPET, ast_feats, metric_feats)

    assert vector.shape == (792,)
    assert embedding.shape == (768,)
    # The first 11 entries must be the AST features, in AST_FEATURE_COLS order.
    expected_ast_prefix = [float(ast_feats[c]) for c in ml_bridge.AST_FEATURE_COLS]
    np.testing.assert_allclose(vector[:11], expected_ast_prefix)
    # The next 13 entries must be the metric features, in METRICS_FEATURE_COLS order.
    expected_metric_block = [float(metric_feats[c]) for c in ml_bridge.METRICS_FEATURE_COLS]
    np.testing.assert_allclose(vector[11:24], expected_metric_block)
    # The final 768 entries must be exactly the CodeBERT embedding, untouched.
    np.testing.assert_allclose(vector[24:], embedding)


def test_github_url_validator_accepts_a_real_https_url():
    # Does not clone anything -- _validate_url is pure string validation.
    result = github_service._validate_url("https://github.com/madler/zlib")
    assert result == "https://github.com/madler/zlib"


def test_github_url_validator_rejects_non_http_schemes():
    for bad_url in ["ssh://git@github.com/x/y.git", "file:///etc/passwd", "git@github.com:x/y.git"]:
        try:
            github_service._validate_url(bad_url)
            assert False, f"expected {bad_url!r} to be rejected"
        except ValueError:
            pass


def test_github_url_validator_rejects_flag_injection_style_strings():
    # A leading "-" could be interpreted as a command-line flag if this
    # string were ever passed through a shell; the validator must reject it
    # outright rather than relying solely on argv-list invocation elsewhere.
    for bad_url in ["--upload-pack=evil", "-oProxyCommand=evil"]:
        try:
            github_service._validate_url(bad_url)
            assert False, f"expected {bad_url!r} to be rejected"
        except ValueError:
            pass


def test_scan_code_endpoint_rejects_empty_code():
    response = client.post("/api/scan/code", json={
        "code": "", "project_name": "test", "filename": "empty.c",
        "model_choice": "XGBoost", "source": "paste",
    })
    assert response.status_code == 400


def test_verdict_threshold_matches_the_validated_constant():
    # Re-selected after the Phase 4 feature-fusion alignment fix
    # (docs/ML_FORENSIC_AUDIT_PHASE4.md) invalidated the dataset used to
    # pick the previous value (0.32). This guards against a regression
    # silently reverting to model.predict()'s implicit 0.5 default, which
    # would undo a real, measured F1 improvement on the CORRECTED dataset
    # (0.5315 -> 0.6361).
    import predictor
    assert predictor.VULNERABILITY_THRESHOLD == 0.26

    for snippet in (VULNERABLE_SNIPPET,):
        result = ml_bridge.run_prediction(snippet, "XGBoost")
        prob_fraction = result["vuln_probability"] / 100.0
        expected_verdict = "VULNERABLE" if prob_fraction >= predictor.VULNERABILITY_THRESHOLD else "NOT VULNERABLE"
        assert result["verdict"] == expected_verdict


def test_github_scan_endpoint_rejects_invalid_url_without_cloning():
    # Validation happens before any git subprocess is spawned, so this must
    # return fast (well under a second) with a 400, not attempt a clone.
    response = client.post("/api/github/scan", json={"repo_url": "not-a-url-at-all"})
    assert response.status_code == 400
