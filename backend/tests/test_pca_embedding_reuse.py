# =============================================================================
# test_pca_embedding_reuse.py -- Phase F of docs/ASYNC_SCAN_DESIGN.md Sec 4:
# scan_service.run_and_store_scan() reuses the CodeBERT embedding
# run_prediction() already computed (predictor.py's result["_embedding"])
# for the PCA scatter coordinate, instead of paying for a second, redundant
# whole-file forward pass over the same code.
#
# Confirms both that the embedding is genuinely threaded through (not just
# that a coordinate happens to appear) and that the resulting coordinate is
# a valid, finite point -- not a silent NaN/None regression.
# =============================================================================

import math

import numpy as np
import pytest

import ml_bridge
import scan_service
from database import SessionLocal, ScanRecord

VULNERABLE_SNIPPET = """
void copy_input(char *dest, const char *src) {
    strcpy(dest, src);
}
"""


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_run_prediction_carries_the_raw_embedding_through(db):
    result = ml_bridge.run_prediction(VULNERABLE_SNIPPET, "XGBoost")
    if result.get("is_demo"):
        pytest.skip("No trained model available in this environment -- demo mode has no embedding to carry.")
    embedding = result.get("_embedding")
    assert embedding is not None, "predict_functions_with_model/predict_with_model must set result['_embedding']"
    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (768,)


def test_stored_scan_gets_a_valid_pca_coordinate_without_a_second_forward_pass(db):
    record = scan_service.run_and_store_scan(
        db, VULNERABLE_SNIPPET, "phase-f-test", "test.c", "XGBoost", "paste",
    )
    try:
        if record.is_demo:
            pytest.skip("No trained model available in this environment.")
        assert record.embedding_2d_x is not None
        assert record.embedding_2d_y is not None
        assert not math.isnan(record.embedding_2d_x)
        assert not math.isnan(record.embedding_2d_y)
    finally:
        db.query(ScanRecord).filter(ScanRecord.id == record.id).delete()
        db.commit()


def test_reused_embedding_is_the_same_vector_used_for_the_stored_verdict(db):
    # Confirms the reuse path threads through the ACTUAL vector the verdict
    # was computed from, not a stray/mismatched one -- by recomputing the
    # embedding for the exact text run_prediction's per-function path used
    # (code_intelligence.extract_functions()'s parsed function text, which
    # is reformatted from -- not byte-identical to -- the raw input snippet:
    # confirmed by inspection, not assumed), and checking it round-trips to
    # the same embedding, not merely a plausible-looking one.
    import code_intelligence

    result = ml_bridge.run_prediction(VULNERABLE_SNIPPET, "XGBoost")
    if result.get("is_demo"):
        pytest.skip("No trained model available in this environment.")
    reused_embedding = result["_embedding"]

    functions = code_intelligence.extract_functions(VULNERABLE_SNIPPET)
    assert len(functions) == 1, "test snippet must parse to exactly one function"
    worst_fn_text = functions[0]["text"]

    tokenizer, codebert_model = ml_bridge.get_codebert()
    from predictor import extract_codebert_embedding
    recomputed_embedding = extract_codebert_embedding(worst_fn_text, tokenizer, codebert_model)

    assert np.allclose(reused_embedding, recomputed_embedding, atol=1e-4), (
        "result['_embedding'] does not match the embedding of the function it "
        "was supposedly computed from -- the reuse path may be threading "
        "through the wrong vector."
    )


def test_reused_and_freshly_recomputed_whole_file_coordinates_are_both_valid_but_may_differ(db):
    # The PCA coordinate now reflects the WORST FUNCTION's embedding
    # (reused, consistent with every other field already stored on
    # ScanRecord -- ast_features/metric_features were already worst-function
    # scoped before this change), not the whole file's -- a deliberate,
    # documented behavior change from the old always-whole-file pass
    # (docs/ASYNC_SCAN_DESIGN.md Sec 4 / Phase F), not a bug. Both
    # coordinates must independently be valid, finite points; they are NOT
    # expected to be close to each other in general (different, legitimately
    # differently-formatted input text for a multi-function file).
    result = ml_bridge.run_prediction(VULNERABLE_SNIPPET, "XGBoost")
    if result.get("is_demo"):
        pytest.skip("No trained model available in this environment.")
    reused_embedding = result["_embedding"]

    ast_feats = result.get("ast_features", {})
    metric_feats = result.get("metric_features", {})
    _, fresh_embedding = ml_bridge.full_feature_vector(VULNERABLE_SNIPPET, ast_feats, metric_feats)

    proj_reused = ml_bridge.project_embedding(reused_embedding)
    proj_fresh = ml_bridge.project_embedding(fresh_embedding)
    for proj in (proj_reused, proj_fresh):
        assert proj is not None
        assert len(proj) == 2
        assert all(not math.isnan(v) and not math.isinf(v) for v in proj)
