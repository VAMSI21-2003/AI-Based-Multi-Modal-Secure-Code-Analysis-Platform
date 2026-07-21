# =============================================================================
# fusion_core.py -- stable-ID feature fusion + explicit alignment validation.
#
# Extracted out of fuse_features.py so it can be imported with ZERO side
# effects (fuse_features.py is a top-level tutorial script that reads real
# files and calls sys.exit() on the way) -- both by that script itself and
# by tests/test_fusion_alignment.py.
#
# See docs/ML_FORENSIC_AUDIT_PHASE4.md for the full forensic finding this
# replaces: the previous version of fuse_features.py assigned sample_id as
# range(len(each_table)) -- i.e. each table's OWN output row position, not a
# stable reference to the original dataset. Since extract_ast_features.py
# and extract_metrics.py used different, inconsistent minimum-length
# filters, their row-position numbering silently desynced, and 99.35% of
# fused rows paired one function's label/AST features with a DIFFERENT
# function's metrics/CodeBERT features.
#
# The fix: every table now carries a stable 'original_id' column, assigned
# exactly once in preprocess_dataset.py and never recomputed downstream.
# fuse_tables() joins on THAT column and validates the result explicitly --
# any duplicate ID, missing ID, or cross-table label/code mismatch raises
# FusionAlignmentError instead of silently producing a misaligned row.
# =============================================================================

import pandas as pd


class FusionAlignmentError(Exception):
    """Raised when the fused feature tables cannot be proven to be correctly aligned."""


def _require_unique_ids(df: pd.DataFrame, table_name: str) -> None:
    if "original_id" not in df.columns:
        raise FusionAlignmentError(f"{table_name} has no 'original_id' column.")
    dup_mask = df["original_id"].duplicated(keep=False)
    if dup_mask.any():
        dup_ids = sorted(df.loc[dup_mask, "original_id"].unique().tolist())
        raise FusionAlignmentError(
            f"{table_name} has {len(dup_ids)} duplicate original_id value(s): {dup_ids[:20]}"
            + (" ... (truncated)" if len(dup_ids) > 20 else "")
        )


def fuse_tables(ast_sel: pd.DataFrame, metrics_sel: pd.DataFrame, codebert_sel: pd.DataFrame) -> pd.DataFrame:
    """
    Joins AST + Metrics + CodeBERT feature tables on the stable
    'original_id' column, with explicit, loud validation at every step.
    Each input must already be reduced to just the columns that belong in
    the final fused table (original_id + its own feature columns, plus
    'target' and 'func' kept on ast_sel/metrics_sel specifically so they
    can be CROSS-VALIDATED against each other post-merge -- if they ever
    disagree for the same original_id, that is direct proof of a remaining
    alignment bug, not something to silently average over).

    original_id is the ONLY join key ever used here. Row position (index)
    is never consulted, so callers may pass these three tables in any row
    order and get an identical result (see
    tests/test_fusion_alignment.py::test_shuffled_row_order_produces_identical_fused_result).

    Raises FusionAlignmentError (never returns a silently-wrong result) if:
      - any table is missing the 'original_id' column entirely,
      - any table has duplicate original_id values,
      - the merged tables share zero original_id values at all (a fully
        disjoint ID space between tables -- e.g. different dataset
        versions),
      - 'target' or 'func' disagree between ast_sel and metrics_sel for the
        same original_id after merging,
      - 'target' disagrees between the AST+Metrics merge and codebert_sel
        (only checked when codebert_sel carries a 'target' column).

    NOTE ON PARTIAL OVERLAP: if the three tables' original_id sets overlap
    only PARTIALLY (some IDs present in one or two tables but not all
    three), that is NOT treated as an error by itself -- an inner join
    correctly keeps only the common IDs, and the exact counts are reported
    in the returned DataFrame's `.attrs["fusion_report"]` (ids_common_all_three,
    ids_missing_from_ast/metrics/codebert, pct_retained_from_intersection)
    so the caller can inspect and decide whether the loss is expected (e.g.
    a smaller CodeBERT MAX_SAMPLES run) or a sign of a real problem. Only a
    COMPLETELY disjoint pair (zero shared IDs) is treated as an outright
    error, because that is not "partial data loss", it is "these tables
    describe different datasets".
    """
    for name, df in (("AST table", ast_sel), ("Metrics table", metrics_sel), ("CodeBERT table", codebert_sel)):
        _require_unique_ids(df, name)

    ast_ids = set(ast_sel["original_id"])
    metrics_ids = set(metrics_sel["original_id"])
    codebert_ids = set(codebert_sel["original_id"])

    all_ids = ast_ids | metrics_ids | codebert_ids
    common_ids = ast_ids & metrics_ids & codebert_ids

    only_in_ast = ast_ids - metrics_ids - codebert_ids
    only_in_metrics = metrics_ids - ast_ids - codebert_ids
    missing_from_all = all_ids - common_ids
    missing_from_ast = all_ids - ast_ids
    missing_from_metrics = all_ids - metrics_ids
    missing_from_codebert = all_ids - codebert_ids

    # Merge 1: AST + Metrics, cross-validating target/func for every row that
    # survives the inner join.
    merged_step1 = pd.merge(
        ast_sel.rename(columns={"target": "target_ast", "func": "func_ast"}),
        metrics_sel.rename(columns={"target": "target_metrics", "func": "func_metrics"}),
        on="original_id", how="inner",
    )
    if len(merged_step1) == 0:
        raise FusionAlignmentError(
            "AST + Metrics merge produced ZERO rows -- original_id values do not "
            "overlap at all between the two tables. This means the tables were "
            "generated from different dataset versions, not a subtle misalignment."
        )

    label_mismatch = merged_step1["target_ast"] != merged_step1["target_metrics"]
    if label_mismatch.any():
        bad_ids = merged_step1.loc[label_mismatch, "original_id"].tolist()
        raise FusionAlignmentError(
            f"{len(bad_ids)} row(s) have a DIFFERENT target label in the AST table "
            f"than in the Metrics table for the same original_id -- this proves "
            f"cross-modal misalignment, not just noise. Affected original_id(s) "
            f"(first 20): {bad_ids[:20]}"
        )

    if "func_ast" in merged_step1.columns and "func_metrics" in merged_step1.columns:
        func_mismatch = merged_step1["func_ast"] != merged_step1["func_metrics"]
        if func_mismatch.any():
            bad_ids = merged_step1.loc[func_mismatch, "original_id"].tolist()
            raise FusionAlignmentError(
                f"{len(bad_ids)} row(s) have DIFFERENT source code text in the AST "
                f"table than in the Metrics table for the same original_id -- this "
                f"is definitive proof of cross-modal misalignment. Affected "
                f"original_id(s) (first 20): {bad_ids[:20]}"
            )
        merged_step1 = merged_step1.drop(columns=["func_metrics"]).rename(columns={"func_ast": "func"})
    merged_step1 = merged_step1.drop(columns=["target_metrics"]).rename(columns={"target_ast": "target"})

    # Merge 2: (AST + Metrics) + CodeBERT, cross-validating target again.
    merged_all = pd.merge(
        merged_step1,
        codebert_sel.rename(columns={"target": "target_codebert"}),
        on="original_id", how="inner",
    )
    if len(merged_all) == 0:
        raise FusionAlignmentError(
            "(AST+Metrics) + CodeBERT merge produced ZERO rows -- original_id "
            "values do not overlap between the merged table and the CodeBERT table."
        )
    if "target_codebert" in merged_all.columns:
        label_mismatch2 = merged_all["target"] != merged_all["target_codebert"]
        if label_mismatch2.any():
            bad_ids = merged_all.loc[label_mismatch2, "original_id"].tolist()
            raise FusionAlignmentError(
                f"{len(bad_ids)} row(s) have a DIFFERENT target label in the "
                f"AST+Metrics merge than in the CodeBERT table for the same "
                f"original_id -- cross-modal misalignment. Affected original_id(s) "
                f"(first 20): {bad_ids[:20]}"
            )
        merged_all = merged_all.drop(columns=["target_codebert"])

    _require_unique_ids(merged_all, "final fused table")

    n_common = len(common_ids)
    pct_retained = (len(merged_all) / n_common * 100.0) if n_common > 0 else 0.0

    merged_all.attrs["fusion_report"] = {
        # Input row counts (== unique ID counts per table, since duplicate
        # original_id values within a single table are rejected above).
        "ast_input_rows": len(ast_sel),
        "metrics_input_rows": len(metrics_sel),
        "codebert_input_rows": len(codebert_sel),
        "unique_ids_ast": len(ast_ids),
        "unique_ids_metrics": len(metrics_ids),
        "unique_ids_codebert": len(codebert_ids),
        # Overlap between the three ID sets.
        "ids_common_all_three": n_common,
        "ids_missing_from_ast": len(missing_from_ast),
        "ids_missing_from_metrics": len(missing_from_metrics),
        "ids_missing_from_codebert": len(missing_from_codebert),
        "only_in_ast": sorted(only_in_ast),
        "only_in_metrics": sorted(only_in_metrics),
        "missing_from_at_least_one_table": len(missing_from_all),
        # Final result.
        "fused_rows": len(merged_all),
        "pct_retained_from_intersection": round(pct_retained, 2),
    }
    return merged_all
