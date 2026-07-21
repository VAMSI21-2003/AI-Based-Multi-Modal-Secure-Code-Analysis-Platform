# =============================================================================
# test_fusion_alignment.py -- regression tests for the Phase 4 feature-fusion
# alignment fix (docs/ML_FORENSIC_AUDIT_PHASE4.md).
#
# The bug: extract_ast_features.py and extract_metrics.py used different
# minimum-length filters (50 vs. 10 chars) and each assigned sample_id as
# ITS OWN output's row position via range(len(df)). The moment either
# script dropped a different set of rows, their sample_id numbering
# silently desynced, causing 99.35% of the real fused dataset to pair one
# function's label/AST features with a different function's metrics/
# CodeBERT features.
#
# The fix (src/fusion/fuse_features.py): every table now carries a stable
# 'original_id' column (never recomputed from local row position), and
# fuse_tables() validates the join explicitly -- raising FusionAlignmentError
# on any duplicate ID, missing modality causing unexpected loss, or
# cross-table target/func mismatch -- rather than silently producing a
# misaligned result.
#
# These tests use small, synthetic DataFrames (not the real 27k-row
# dataset) specifically so they run in milliseconds and exercise exact,
# controlled scenarios.
# =============================================================================

import os
import sys

import pandas as pd
import pytest

FUSION_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "fusion")
if FUSION_DIR not in sys.path:
    sys.path.insert(0, FUSION_DIR)

from fusion_core import fuse_tables, FusionAlignmentError  # noqa: E402


def _make_tables(n=6, ast_drop_ids=(), metrics_drop_ids=(), codebert_drop_ids=(), shuffle=False, seed=0):
    """
    Builds three small, synthetic, ALIGNED feature tables for n original
    samples (original_id 0..n-1), each with a genuinely distinct 'func'
    string and a genuinely distinct AST/metric/embedding value derived from
    original_id -- so any misalignment is immediately and deterministically
    detectable (function text and feature values will disagree).
    """
    base = pd.DataFrame({
        "original_id": list(range(n)),
        "func": [f"void f{i}(void) {{ return {i}; }}" for i in range(n)],
        "target": [i % 2 for i in range(n)],
    })

    ast = base.copy()
    ast["n_loops"] = ast["original_id"]  # distinct per-sample "AST feature"
    ast = ast[~ast["original_id"].isin(ast_drop_ids)].reset_index(drop=True)

    metrics = base.copy()
    metrics["loc"] = metrics["original_id"] * 10  # distinct per-sample "metric feature"
    metrics = metrics[~metrics["original_id"].isin(metrics_drop_ids)].reset_index(drop=True)

    codebert = base[["original_id", "target"]].copy()
    codebert["embed_000"] = codebert["original_id"] * 100.0  # distinct per-sample "embedding"
    codebert = codebert[~codebert["original_id"].isin(codebert_drop_ids)].reset_index(drop=True)

    if shuffle:
        ast = ast.sample(frac=1, random_state=seed).reset_index(drop=True)
        metrics = metrics.sample(frac=1, random_state=seed + 1).reset_index(drop=True)
        codebert = codebert.sample(frac=1, random_state=seed + 2).reset_index(drop=True)

    return ast, metrics, codebert


def test_fully_aligned_tables_fuse_correctly():
    ast, metrics, codebert = _make_tables(n=6)
    fused = fuse_tables(ast, metrics, codebert)
    assert len(fused) == 6
    # For every fused row, the AST-derived feature, metric-derived feature,
    # and embedding must all trace back to the SAME original_id.
    for _, row in fused.iterrows():
        oid = row["original_id"]
        assert row["n_loops"] == oid
        assert row["loc"] == oid * 10
        assert row["embed_000"] == oid * 100.0
        assert row["func"] == f"void f{oid}(void) {{ return {oid}; }}"


def test_short_function_dropped_by_ast_but_kept_by_metrics_cannot_misalign():
    # This is the EXACT real-world scenario from the forensic audit: a
    # sample that one script drops and another keeps must NOT cause every
    # subsequent original_id to silently pair with the wrong function. With
    # the stable-ID join, a dropped sample simply falls out of the inner
    # join (reported, not hidden) -- every SURVIVING sample must still be
    # correctly paired.
    ast, metrics, codebert = _make_tables(n=10, ast_drop_ids=(3,))
    fused = fuse_tables(ast, metrics, codebert)
    # original_id 3 is correctly excluded (only in metrics/codebert, not AST)
    assert 3 not in fused["original_id"].values
    assert len(fused) == 9
    # Every surviving sample must still be correctly paired -- this is the
    # actual regression check: verify original_id 4..9 (the ones that used
    # to shift by one position in the old range()-based bug) still have
    # matching, correct feature values.
    for _, row in fused.iterrows():
        oid = row["original_id"]
        assert row["n_loops"] == oid
        assert row["loc"] == oid * 10
        assert row["func"] == f"void f{oid}(void) {{ return {oid}; }}"


def test_shuffled_row_order_produces_identical_fused_result():
    # The join must be by VALUE (original_id), not by position -- feeding in
    # the three tables in scrambled row order must produce the exact same
    # correct pairing as the unshuffled version.
    ast_a, metrics_a, codebert_a = _make_tables(n=8, shuffle=False)
    ast_b, metrics_b, codebert_b = _make_tables(n=8, shuffle=True, seed=42)

    fused_a = fuse_tables(ast_a, metrics_a, codebert_a).sort_values("original_id").reset_index(drop=True)
    fused_b = fuse_tables(ast_b, metrics_b, codebert_b).sort_values("original_id").reset_index(drop=True)

    pd.testing.assert_frame_equal(
        fused_a[["original_id", "n_loops", "loc", "embed_000", "func"]],
        fused_b[["original_id", "n_loops", "loc", "embed_000", "func"]],
    )


def test_labels_remain_correctly_aligned_after_fusion():
    ast, metrics, codebert = _make_tables(n=6)
    fused = fuse_tables(ast, metrics, codebert)
    for _, row in fused.iterrows():
        assert row["target"] == row["original_id"] % 2


def test_duplicate_original_id_in_one_table_is_detected_and_raises():
    ast, metrics, codebert = _make_tables(n=5)
    ast = pd.concat([ast, ast.iloc[[0]]], ignore_index=True)  # duplicate original_id=0
    with pytest.raises(FusionAlignmentError, match="duplicate"):
        fuse_tables(ast, metrics, codebert)


def test_missing_modality_entirely_is_detected_not_silently_zero_rows():
    # If original_id sets don't overlap AT ALL between two tables, that's a
    # gross error (different dataset versions), not a subtle bug -- must
    # raise loudly, not return an empty DataFrame silently.
    ast, metrics, codebert = _make_tables(n=5)
    ast["original_id"] = ast["original_id"] + 1000  # completely disjoint ID space
    with pytest.raises(FusionAlignmentError, match="ZERO rows"):
        fuse_tables(ast, metrics, codebert)


def test_cross_table_label_mismatch_is_detected_and_raises():
    # Simulates a residual alignment bug slipping through: same original_id,
    # but a different target in two tables for it. Must be caught, not
    # averaged over or silently trusting one side.
    ast, metrics, codebert = _make_tables(n=5)
    metrics.loc[metrics["original_id"] == 2, "target"] = 1 - metrics.loc[metrics["original_id"] == 2, "target"]
    with pytest.raises(FusionAlignmentError, match="target label"):
        fuse_tables(ast, metrics, codebert)


def test_cross_table_func_mismatch_is_detected_and_raises():
    ast, metrics, codebert = _make_tables(n=5)
    metrics.loc[metrics["original_id"] == 2, "func"] = "void tampered(void) {}"
    with pytest.raises(FusionAlignmentError, match="source code text"):
        fuse_tables(ast, metrics, codebert)


def test_cross_table_codebert_target_mismatch_is_detected_and_raises():
    # Same real-world failure mode as the AST/Metrics label mismatch test,
    # but on the SECOND merge (AST+Metrics result joined against CodeBERT).
    # A residual bug here would mean the CodeBERT branch alone drifted out
    # of alignment even though AST and Metrics still agree with each other.
    ast, metrics, codebert = _make_tables(n=5)
    codebert.loc[codebert["original_id"] == 2, "target"] = (
        1 - codebert.loc[codebert["original_id"] == 2, "target"]
    )
    with pytest.raises(FusionAlignmentError, match="target label"):
        fuse_tables(ast, metrics, codebert)


def test_missing_original_id_column_is_detected_and_raises():
    # A table that never had 'original_id' at all (e.g. an old, unfixed
    # extraction script's output) must be rejected outright, not silently
    # treated as if it had zero rows or joined by position.
    ast, metrics, codebert = _make_tables(n=5)
    ast_no_id = ast.drop(columns=["original_id"])
    with pytest.raises(FusionAlignmentError, match="no 'original_id' column"):
        fuse_tables(ast_no_id, metrics, codebert)


def test_completely_disjoint_original_id_sets_raise():
    # Same scenario as test_missing_modality_entirely_is_detected_not_silently_zero_rows
    # stated explicitly per the two tables having NO original_id in common at
    # all -- this must never silently return an empty (0-row) DataFrame.
    ast, metrics, codebert = _make_tables(n=5)
    ast["original_id"] = ast["original_id"] + 1000
    metrics["original_id"] = metrics["original_id"] + 2000
    with pytest.raises(FusionAlignmentError, match="ZERO rows"):
        fuse_tables(ast, metrics, codebert)


def test_partially_overlapping_tables_produce_expected_intersection_and_report():
    # original_id 0..9 exist everywhere, but AST is missing {2, 5} and
    # Metrics is missing {7}. This is real, expected data loss (not a bug),
    # so it must NOT raise -- but the fusion report must precisely account
    # for every dropped ID so the caller can verify none of it is silent.
    ast, metrics, codebert = _make_tables(n=10, ast_drop_ids=(2, 5), metrics_drop_ids=(7,))
    fused = fuse_tables(ast, metrics, codebert)

    expected_surviving = {0, 1, 3, 4, 6, 8, 9}  # 10 ids minus {2,5,7}
    assert set(fused["original_id"].tolist()) == expected_surviving
    assert len(fused) == 7

    report = fused.attrs["fusion_report"]
    assert report["ast_input_rows"] == 8       # 10 - {2, 5}
    assert report["metrics_input_rows"] == 9   # 10 - {7}
    assert report["codebert_input_rows"] == 10
    assert report["unique_ids_ast"] == 8
    assert report["unique_ids_metrics"] == 9
    assert report["unique_ids_codebert"] == 10
    assert report["ids_common_all_three"] == 7
    assert report["ids_missing_from_ast"] == 2       # {2, 5}
    assert report["ids_missing_from_metrics"] == 1   # {7}
    assert report["ids_missing_from_codebert"] == 0
    assert report["fused_rows"] == 7
    assert report["pct_retained_from_intersection"] == 100.0


def test_row_order_differing_between_modalities_still_aligns_correctly():
    # The three tables are handed to fuse_tables() in genuinely different,
    # unrelated row orders (not just "all shuffled the same way") -- the
    # result must still pair every original_id with its own correct
    # AST/metric/embedding values, proving the join uses original_id values,
    # never each table's row position.
    ast, metrics, codebert = _make_tables(n=8)
    ast = ast.iloc[::-1].reset_index(drop=True)                      # reversed
    metrics = metrics.sample(frac=1, random_state=99).reset_index(drop=True)  # shuffled
    # codebert left in original ascending order

    fused = fuse_tables(ast, metrics, codebert)
    assert len(fused) == 8
    for _, row in fused.iterrows():
        oid = row["original_id"]
        assert row["n_loops"] == oid
        assert row["loc"] == oid * 10
        assert row["embed_000"] == oid * 100.0
        assert row["func"] == f"void f{oid}(void) {{ return {oid}; }}"
