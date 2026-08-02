# =============================================================================
# grouped_split.py -- PHASE 2: commit-aware (grouped) split over the ALREADY-
# FUSED, ALREADY-ALIGNMENT-FIXED feature table (dataset/processed/final_features.csv).
#
# This script does NOT touch extraction, fuse_features.py, fusion_core.py, or
# the alignment logic in any way -- it only reads the existing fused CSV. It
# tests the leakage concern docs/ML_FORENSIC_AUDIT_PHASE4.md flagged but did
# not measure: the production baseline (F1=0.5391, AUC=0.6346, from a plain
# stratify=y-only random split) has NO mechanism preventing same-commit rows
# from appearing on both sides of train/test. With 12,290 commits (mean 2.22
# rows/commit, one commit contributing 588 rows -- see
# src/model/verify_commit_grouping.py / docs, Phase 0 of this same session)
# that is structurally very likely to happen on a random split.
#
# Methodology:
#   - StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42) on
#     final_features.csv's own commit_id column (verified correct against an
#     independent join in Phase 0), so no two rows from the same commit ever
#     appear on both sides of a fold boundary. Explicitly asserted per fold,
#     not just assumed from the API's contract.
#   - Same XGBoost hyperparameters as production: n_estimators=100,
#     max_depth=6, learning_rate=0.1, random_state=42, scale_pos_weight
#     computed per fold from that fold's own y_train.
#   - Full-fusion (792-dim) feature set only -- this experiment is about
#     whether the SPLIT changes results, not about re-running the modality
#     comparison (that's Phase 1 / cross_validation.py).
#   - Directly compared against the current production baseline, a single
#     random stratified 80/20 split (F1=0.5391, AUC=0.6346 --
#     models/training_metadata.json).
#
# Run: python src/model/grouped_split.py
# =============================================================================

import json
import os
import time

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from xgboost import XGBClassifier

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
FINAL_CSV = os.path.join(PROJECT_ROOT, "dataset", "processed", "final_features.csv")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results", "experiments")
OUT_JSON = os.path.join(RESULTS_DIR, "grouped_split.json")

N_SPLITS = 5
RANDOM_STATE = 42
N_ESTIMATORS = 100

# Production baseline this experiment is compared against -- a single random
# stratified 80/20 split with NO commit grouping (models/training_metadata.json,
# reproduced exactly by modality_ablation.py's "Full fusion" row).
BASELINE_F1 = 0.5391
BASELINE_AUC = 0.6346
BASELINE_ACCURACY = 0.5932
BASELINE_PRECISION = 0.5574
BASELINE_RECALL = 0.5219

METADATA_COLS = ["sample_id", "target", "project", "commit_id", "func"]


def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    t_start = time.time()

    section("LOAD final_features.csv (already fused, already alignment-fixed)")
    df = pd.read_csv(FINAL_CSV, encoding="utf-8")
    print(f"  Rows   : {len(df)}")
    print(f"  Columns: {len(df.columns)}")

    y = df["target"].values
    groups = df["commit_id"].values
    feature_cols = [c for c in df.columns if c not in METADATA_COLS]
    assert len(feature_cols) == 792
    X = df[feature_cols].values
    if np.isnan(X).sum() > 0:
        X = np.nan_to_num(X, nan=0.0)
    print(f"  Full-fusion feature matrix: {X.shape}")
    print(f"  Distinct commit_id groups : {len(np.unique(groups))}")

    section(f"STRATIFIED-GROUP {N_SPLITS}-FOLD SPLIT (grouped on commit_id)")
    sgkf = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    folds = list(sgkf.split(X, y, groups=groups))

    for i, (tr, te) in enumerate(folds):
        train_groups = set(groups[tr])
        test_groups = set(groups[te])
        overlap = train_groups & test_groups
        n_safe_tr, n_vuln_tr = int((y[tr] == 0).sum()), int((y[tr] == 1).sum())
        n_safe_te, n_vuln_te = int((y[te] == 0).sum()), int((y[te] == 1).sum())
        print(f"  Fold {i}: train={len(tr)} rows / {len(train_groups)} commits "
              f"(safe={n_safe_tr}, vuln={n_vuln_tr})  "
              f"test={len(te)} rows / {len(test_groups)} commits "
              f"(safe={n_safe_te}, vuln={n_vuln_te})")
        assert len(overlap) == 0, (
            f"STOP: fold {i} has {len(overlap)} commit_id(s) appearing in BOTH train and "
            f"test -- grouping failed, this is exactly the leakage this experiment is "
            f"supposed to eliminate. First few: {list(overlap)[:10]}"
        )
    print(f"  PASS: verified directly (not assumed from the API contract) -- across all "
          f"{N_SPLITS} folds, ZERO commit_id values appear on both sides of a fold boundary.")

    # Sanity: also directly verify at the ROW level for fold 0 as an extra check
    # (redundant with the group-set check above, but proves it a second way).
    tr0, te0 = folds[0]
    row_check = pd.DataFrame({"idx": np.concatenate([tr0, te0]),
                               "commit_id": np.concatenate([groups[tr0], groups[te0]]),
                               "split": ["train"] * len(tr0) + ["test"] * len(te0)})
    pivot = row_check.groupby("commit_id")["split"].nunique()
    n_commits_in_both = int((pivot > 1).sum())
    assert n_commits_in_both == 0, f"STOP: {n_commits_in_both} commits split across train/test in fold 0 (row-level check)."
    print(f"  PASS (row-level re-check on fold 0): 0 commits split across train/test.")

    def run_fold(tr, te):
        X_train, X_test = X[tr], X[te]
        y_train, y_test = y[tr], y[te]
        n_safe = int((y_train == 0).sum())
        n_vuln = int((y_train == 1).sum())
        scale_pos_weight = round(n_safe / max(n_vuln, 1), 2)

        model = XGBClassifier(
            n_estimators=N_ESTIMATORS,
            max_depth=6,
            learning_rate=0.1,
            scale_pos_weight=scale_pos_weight,
            random_state=RANDOM_STATE,
            verbosity=0,
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]

        return {
            "scale_pos_weight": scale_pos_weight,
            "n_train": int(len(tr)),
            "n_test": int(len(te)),
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1": float(f1_score(y_test, y_pred, zero_division=0)),
            "auc": float(roc_auc_score(y_test, y_proba)),
        }

    section(f"TRAINING XGBOOST ON EACH GROUPED FOLD (full fusion, {X.shape[1]} features)")
    fold_metrics = []
    for i, (tr, te) in enumerate(folds):
        t0 = time.time()
        r = run_fold(tr, te)
        r["fold"] = i
        fold_metrics.append(r)
        print(f"  Fold {i}: Accuracy={r['accuracy']:.4f}  Precision={r['precision']:.4f}  "
              f"Recall={r['recall']:.4f}  F1={r['f1']:.4f}  AUC={r['auc']:.4f}  "
              f"({time.time() - t0:.1f}s)")

    def mean_std(key):
        vals = np.array([m[key] for m in fold_metrics])
        return float(vals.mean()), float(vals.std(ddof=1)), float(vals.std(ddof=1) / np.sqrt(len(vals)))

    summary = {}
    for key in ("accuracy", "precision", "recall", "f1", "auc"):
        mean, std, se = mean_std(key)
        summary[key] = {"mean": round(mean, 4), "std": round(std, 4), "se": round(se, 4)}

    section("SUMMARY: grouped (commit-aware) 5-fold CV, full fusion")
    print(f"  Accuracy  = {summary['accuracy']['mean']:.4f} +/- {summary['accuracy']['std']:.4f}")
    print(f"  Precision = {summary['precision']['mean']:.4f} +/- {summary['precision']['std']:.4f}")
    print(f"  Recall    = {summary['recall']['mean']:.4f} +/- {summary['recall']['std']:.4f}")
    print(f"  F1        = {summary['f1']['mean']:.4f} +/- {summary['f1']['std']:.4f}  (SE={summary['f1']['se']:.4f})")
    print(f"  AUC       = {summary['auc']['mean']:.4f} +/- {summary['auc']['std']:.4f}  (SE={summary['auc']['se']:.4f})")

    section("DIRECT COMPARISON: grouped split vs. production baseline (random, ungrouped split)")
    f1_drop = summary["f1"]["mean"] - BASELINE_F1
    auc_drop = summary["auc"]["mean"] - BASELINE_AUC
    print(f"  {'Metric':<12} {'Baseline (random split)':>26} {'Grouped CV mean':>18} {'Difference':>12}")
    print(f"  {'-'*70}")
    print(f"  {'Accuracy':<12} {BASELINE_ACCURACY:>26.4f} {summary['accuracy']['mean']:>18.4f} "
          f"{summary['accuracy']['mean'] - BASELINE_ACCURACY:>+12.4f}")
    print(f"  {'Precision':<12} {BASELINE_PRECISION:>26.4f} {summary['precision']['mean']:>18.4f} "
          f"{summary['precision']['mean'] - BASELINE_PRECISION:>+12.4f}")
    print(f"  {'Recall':<12} {BASELINE_RECALL:>26.4f} {summary['recall']['mean']:>18.4f} "
          f"{summary['recall']['mean'] - BASELINE_RECALL:>+12.4f}")
    print(f"  {'F1':<12} {BASELINE_F1:>26.4f} {summary['f1']['mean']:>18.4f} {f1_drop:>+12.4f}")
    print(f"  {'AUC':<12} {BASELINE_AUC:>26.4f} {summary['auc']['mean']:>18.4f} {auc_drop:>+12.4f}")
    print(f"\n  F1 change relative to baseline: {f1_drop:+.4f} ({100 * f1_drop / BASELINE_F1:+.2f}%)")
    print(f"  AUC change relative to baseline: {auc_drop:+.4f} ({100 * auc_drop / BASELINE_AUC:+.2f}%)")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "n_splits": N_SPLITS,
            "random_state": RANDOM_STATE,
            "n_estimators": N_ESTIMATORS,
            "n_rows": int(len(df)),
            "n_features": int(X.shape[1]),
            "n_distinct_commits": int(len(np.unique(groups))),
            "fold_metrics": fold_metrics,
            "summary": summary,
            "baseline_comparison": {
                "baseline_f1": BASELINE_F1,
                "baseline_auc": BASELINE_AUC,
                "baseline_accuracy": BASELINE_ACCURACY,
                "baseline_precision": BASELINE_PRECISION,
                "baseline_recall": BASELINE_RECALL,
                "grouped_f1_mean": summary["f1"]["mean"],
                "grouped_auc_mean": summary["auc"]["mean"],
                "f1_difference": round(f1_drop, 4),
                "auc_difference": round(auc_drop, 4),
            },
        }, f, indent=2)
    print(f"\n  Results saved: {OUT_JSON}")
    print(f"  Total runtime: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
