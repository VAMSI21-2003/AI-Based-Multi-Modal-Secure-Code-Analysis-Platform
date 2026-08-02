# =============================================================================
# grouped_split_codebert_only.py -- follow-up to PHASE 2 (grouped_split.py):
# the SAME commit-aware grouped split, run on the CodeBERT-only (768-dim)
# feature subset, to directly compare against the full-fusion grouped-split
# result already measured this session.
#
# This script does NOT touch extraction, fuse_features.py, fusion_core.py, or
# the alignment logic in any way -- it only reads the already-fused,
# already-alignment-fixed dataset/processed/final_features.csv and its
# commit_id column (verified correct in src/model/verify_commit_grouping.py,
# Phase 0). Nothing in models/, app/predictor.py's VULNERABILITY_THRESHOLD
# (0.26), or the live app is touched.
#
# "Same fold assignment as the full-fusion grouped-split run": confirmed
# structurally, not just claimed -- sklearn's StratifiedGroupKFold computes
# fold membership from y and groups only (verified against the sklearn 1.x
# source: _iter_test_indices never reads X's values, only its length for
# validation). Calling it with the identical n_splits/random_state/shuffle,
# same y (target), and same groups (commit_id), in the same row order,
# reproduces the IDENTICAL fold assignment regardless of which feature
# columns are sliced into X. This is asserted below against the row/commit
# counts recorded in results/experiments/grouped_split.json from the
# full-fusion run, not just assumed.
#
# Run: python src/model/grouped_split_codebert_only.py
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
OUT_JSON = os.path.join(RESULTS_DIR, "grouped_split_codebert_only.json")
PRIOR_JSON = os.path.join(RESULTS_DIR, "grouped_split.json")  # full-fusion grouped-split, this session

N_SPLITS = 5
RANDOM_STATE = 42
N_ESTIMATORS = 100

# Reference numbers this comparison is built around.
BASELINE_FULL_FUSION_RANDOM_F1 = 0.5391
BASELINE_FULL_FUSION_RANDOM_AUC = 0.6346
BASELINE_CODEBERT_RANDOM_F1 = 0.5418  # modality_ablation.py, single 80/20 split
BASELINE_CODEBERT_RANDOM_AUC = 0.6309

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

    y = df["target"].values
    groups = df["commit_id"].values
    feature_cols = [c for c in df.columns if c not in METADATA_COLS]
    emb_cols = [c for c in feature_cols if c.startswith("embed_")]
    assert len(emb_cols) == 768, f"expected 768 CodeBERT columns, got {len(emb_cols)}"
    X = df[emb_cols].values
    if np.isnan(X).sum() > 0:
        X = np.nan_to_num(X, nan=0.0)
    print(f"  CodeBERT-only feature matrix: {X.shape}")

    section(f"STRATIFIED-GROUP {N_SPLITS}-FOLD SPLIT (grouped on commit_id -- must match the "
            f"full-fusion grouped-split run exactly)")
    sgkf = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    folds = list(sgkf.split(X, y, groups=groups))

    for i, (tr, te) in enumerate(folds):
        train_groups = set(groups[tr])
        test_groups = set(groups[te])
        overlap = train_groups & test_groups
        assert len(overlap) == 0, (
            f"STOP: fold {i} has {len(overlap)} commit_id(s) in both train and test."
        )
        print(f"  Fold {i}: train={len(tr)} rows / {len(train_groups)} commits, "
              f"test={len(te)} rows / {len(test_groups)} commits")
    print(f"  PASS: zero commit_id values on both sides of any fold boundary "
          f"(same check as the full-fusion run).")

    section("VERIFY this is the SAME fold assignment as the full-fusion grouped-split run")
    if os.path.exists(PRIOR_JSON):
        with open(PRIOR_JSON, "r", encoding="utf-8") as f:
            prior = json.load(f)
        prior_sizes = [(m["n_train"], m["n_test"]) for m in sorted(prior["fold_metrics"], key=lambda m: m["fold"])]
        this_sizes = [(len(tr), len(te)) for tr, te in folds]
        print(f"  Full-fusion run fold sizes (train, test): {prior_sizes}")
        print(f"  This run's fold sizes      (train, test): {this_sizes}")
        assert prior_sizes == this_sizes, (
            "STOP: fold sizes differ from the recorded full-fusion grouped-split run -- "
            "this is NOT the same fold assignment, the comparison would be invalid."
        )
        assert prior.get("random_state") == RANDOM_STATE and prior.get("n_splits") == N_SPLITS, (
            "STOP: random_state/n_splits differ from the prior run's recorded parameters."
        )
        print(f"  PASS: fold sizes match {PRIOR_JSON} exactly, and random_state/n_splits are "
              f"identical. Since StratifiedGroupKFold's fold assignment is a deterministic "
              f"function of (y, groups, n_splits, random_state, shuffle) only -- verified "
              f"against the sklearn source, X's values are never read -- this confirms the "
              f"SAME fold assignment as the full-fusion run, not merely a similarly-configured "
              f"new one.")
    else:
        print(f"  WARNING: {PRIOR_JSON} not found -- cannot cross-check against the full-fusion "
              f"run's recorded fold sizes. Proceeding, but the 'same fold assignment' claim is "
              f"unverified this run.")

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

    section(f"TRAINING XGBOOST ON EACH GROUPED FOLD (CodeBERT-only, {X.shape[1]} features)")
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

    section("SUMMARY: grouped (commit-aware) 5-fold CV, CodeBERT-only")
    print(f"  F1  = {summary['f1']['mean']:.4f} +/- {summary['f1']['std']:.4f}  (SE={summary['f1']['se']:.4f})")
    print(f"  AUC = {summary['auc']['mean']:.4f} +/- {summary['auc']['std']:.4f}  (SE={summary['auc']['se']:.4f})")

    section("FOUR-WAY COMPARISON")
    full_fusion_grouped_f1 = prior["summary"]["f1"]["mean"] if os.path.exists(PRIOR_JSON) else None
    full_fusion_grouped_auc = prior["summary"]["auc"]["mean"] if os.path.exists(PRIOR_JSON) else None
    print(f"  {'Config':<32} {'Split':<12} {'F1':>10} {'AUC':>10}")
    print(f"  {'-'*66}")
    print(f"  {'Full fusion':<32} {'random':<12} {BASELINE_FULL_FUSION_RANDOM_F1:>10.4f} {BASELINE_FULL_FUSION_RANDOM_AUC:>10.4f}")
    if full_fusion_grouped_f1 is not None:
        print(f"  {'Full fusion':<32} {'grouped':<12} {full_fusion_grouped_f1:>10.4f} {full_fusion_grouped_auc:>10.4f}")
    print(f"  {'CodeBERT-only':<32} {'random':<12} {BASELINE_CODEBERT_RANDOM_F1:>10.4f} {BASELINE_CODEBERT_RANDOM_AUC:>10.4f}")
    print(f"  {'CodeBERT-only':<32} {'grouped':<12} {summary['f1']['mean']:>10.4f} {summary['auc']['mean']:>10.4f}")

    if full_fusion_grouped_f1 is not None:
        gap_f1 = full_fusion_grouped_f1 - summary["f1"]["mean"]
        gap_auc = full_fusion_grouped_auc - summary["auc"]["mean"]
        print(f"\n  Grouped-split gap (full fusion - CodeBERT-only): F1 {gap_f1:+.4f}, AUC {gap_auc:+.4f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "n_splits": N_SPLITS,
            "random_state": RANDOM_STATE,
            "n_estimators": N_ESTIMATORS,
            "n_rows": int(len(df)),
            "n_features": int(X.shape[1]),
            "fold_metrics": fold_metrics,
            "summary": summary,
            "four_way_comparison": {
                "full_fusion_random_f1": BASELINE_FULL_FUSION_RANDOM_F1,
                "full_fusion_random_auc": BASELINE_FULL_FUSION_RANDOM_AUC,
                "full_fusion_grouped_f1": full_fusion_grouped_f1,
                "full_fusion_grouped_auc": full_fusion_grouped_auc,
                "codebert_random_f1": BASELINE_CODEBERT_RANDOM_F1,
                "codebert_random_auc": BASELINE_CODEBERT_RANDOM_AUC,
                "codebert_grouped_f1": summary["f1"]["mean"],
                "codebert_grouped_auc": summary["auc"]["mean"],
            },
        }, f, indent=2)
    print(f"\n  Results saved: {OUT_JSON}")
    print(f"  Total runtime: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
