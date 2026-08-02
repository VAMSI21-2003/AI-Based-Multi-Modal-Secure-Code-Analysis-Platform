# =============================================================================
# verify_commit_grouping.py -- PHASE 0 of the CV / grouped-split experiment.
#
# Read-only verification, before any experiment training code is written:
#   1. Confirm final_features.csv's 'sample_id' (== 'original_id' from
#      fusion, per fusion_core.py's rename at merge time) can be joined back
#      to devign_cleaned.csv's 'original_id' to independently recover a
#      commit_id for every single row -- and that this independently-joined
#      commit_id agrees, row for row, with the commit_id ALREADY present in
#      final_features.csv (it is not taken on faith).
#   2. Re-measure commit-count/skew directly from the real, current data --
#      not copied from docs/ML_FORENSIC_AUDIT_PHASE4.md's prior numbers.
#
# Does NOT touch extraction, fuse_features.py, fusion_core.py, the 0.26
# threshold, the production models, or paper/report content. Pure read +
# report.
#
# Run: python src/model/verify_commit_grouping.py
# =============================================================================

import os

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
FINAL_CSV = os.path.join(PROJECT_ROOT, "dataset", "processed", "final_features.csv")
CLEANED_CSV = os.path.join(PROJECT_ROOT, "dataset", "processed", "devign_cleaned.csv")


def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    section("LOAD final_features.csv (metadata columns only, for speed)")
    fused = pd.read_csv(FINAL_CSV, encoding="utf-8", usecols=["sample_id", "target", "project", "commit_id", "func"])
    print(f"  Rows: {len(fused)}")
    print(f"  sample_id dtype: {fused['sample_id'].dtype}, "
          f"range [{fused['sample_id'].min()}, {fused['sample_id'].max()}]")
    print(f"  Duplicate sample_id values: {int(fused['sample_id'].duplicated().sum())}")

    section("LOAD devign_cleaned.csv (the pre-fusion source of original_id + commit_id)")
    cleaned = pd.read_csv(CLEANED_CSV, encoding="utf-8", usecols=["original_id", "commit_id", "project"])
    print(f"  Rows: {len(cleaned)}")
    print(f"  Duplicate original_id values: {int(cleaned['original_id'].duplicated().sum())}")

    section("JOIN final_features.csv.sample_id -> devign_cleaned.csv.original_id")
    joined = fused.merge(
        cleaned, left_on="sample_id", right_on="original_id", how="left",
        suffixes=("_fused", "_cleaned"),
    )
    n_unmatched = int(joined["original_id"].isna().sum())
    print(f"  Rows after left-join: {len(joined)} (expected {len(fused)})")
    print(f"  Rows with NO match in devign_cleaned.csv: {n_unmatched}")
    if n_unmatched == 0:
        print("  PASS: every row in final_features.csv joins back to devign_cleaned.csv "
              "via sample_id == original_id. A commit identifier is recoverable for "
              "every single row, independently of the commit_id already carried in "
              "final_features.csv.")
    else:
        print("  FAIL: some rows do NOT join back -- commit identifier is NOT recoverable "
              "for every row. This must be resolved before any grouped split (Phase 2).")

    section("CROSS-CHECK: does the already-present commit_id in final_features.csv "
            "AGREE with the independently-joined commit_id from devign_cleaned.csv?")
    mismatch_mask = (joined["commit_id_fused"] != joined["commit_id_cleaned"]) & joined["original_id"].notna()
    n_mismatch = int(mismatch_mask.sum())
    print(f"  Rows where commit_id differs between final_features.csv and the fresh join: {n_mismatch}")
    if n_mismatch == 0:
        print("  PASS: the commit_id column already in final_features.csv is not just present -- "
              "it is VERIFIED CORRECT against an independent join on the pre-fusion source table. "
              "Safe to use final_features.csv's own commit_id directly for grouping in Phase 2.")
    else:
        print(f"  MISMATCH on {n_mismatch} rows -- sample commit_id disagreements:")
        print(joined.loc[mismatch_mask, ["sample_id", "commit_id_fused", "commit_id_cleaned"]].head(10))

    project_mismatch_mask = (joined["project_fused"] != joined["project_cleaned"]) & joined["original_id"].notna()
    n_project_mismatch = int(project_mismatch_mask.sum())
    print(f"  Rows where project differs between final_features.csv and the fresh join: {n_project_mismatch}")

    section("COMMIT-COUNT / SKEW -- measured directly on final_features.csv's own commit_id "
            "(the column Phase 2 will actually group on), fresh, not assumed from a prior audit")
    commit_counts = fused["commit_id"].value_counts()
    n_distinct = int(commit_counts.shape[0])
    mean_rows_per_commit = float(commit_counts.mean())
    median_rows_per_commit = float(commit_counts.median())
    max_commit_id = commit_counts.idxmax()
    max_rows = int(commit_counts.max())
    max_pct = 100.0 * max_rows / len(fused)

    print(f"  Total rows                         : {len(fused)}")
    print(f"  Distinct commit_id values          : {n_distinct}")
    print(f"  Mean rows per commit               : {mean_rows_per_commit:.4f}")
    print(f"  Median rows per commit             : {median_rows_per_commit:.1f}")
    print(f"  Max rows from a single commit      : {max_rows} (commit_id={max_commit_id}), "
          f"{max_pct:.2f}% of all rows")
    print(f"  Commits with exactly 1 row (no group risk): "
          f"{int((commit_counts == 1).sum())} ({100.0 * (commit_counts == 1).sum() / n_distinct:.1f}% of commits)")
    print(f"  Commits with >1 row (real grouping needed): "
          f"{int((commit_counts > 1).sum())} ({100.0 * (commit_counts > 1).sum() / n_distinct:.1f}% of commits)")

    section("PRIOR AUDIT CLAIM (docs/ML_FORENSIC_AUDIT_PHASE4.md) vs. THIS SESSION'S FRESH MEASUREMENT")
    print(f"  {'Metric':<32} {'Prior audit':>15} {'This session':>15}")
    print(f"  {'-'*64}")
    print(f"  {'Distinct commits':<32} {'~12,290':>15} {n_distinct:>15,}")
    print(f"  {'Mean rows/commit':<32} {'~2.2':>15} {mean_rows_per_commit:>15.2f}")
    print(f"  {'Max single-commit rows':<32} {'~588':>15} {max_rows:>15,}")

    section("DONE -- Phase 0 verification complete")


if __name__ == "__main__":
    main()
