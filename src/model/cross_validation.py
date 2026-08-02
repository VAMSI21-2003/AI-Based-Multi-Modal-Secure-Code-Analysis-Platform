# =============================================================================
# cross_validation.py -- PHASE 1: k-fold cross-validation over the ALREADY-
# FUSED, ALREADY-ALIGNMENT-FIXED feature table (dataset/processed/final_features.csv).
#
# This script does NOT touch extraction, fuse_features.py, fusion_core.py, or
# the alignment logic in any way -- it only reads the existing fused CSV and
# column-slices it, exactly like src/model/modality_ablation.py. It exists to
# resolve the one question that single 80/20 split couldn't: does full fusion
# (792-dim) actually beat CodeBERT-alone (768-dim) by more than sampling
# noise, or are they statistically indistinguishable? (modality_ablation.py's
# single split: full fusion F1=0.5391 vs CodeBERT-alone F1=0.5418 -- within
# ~1 point, explicitly flagged there as needing CV to resolve.)
#
# Methodology:
#   - StratifiedKFold(n_splits=5, shuffle=True, random_state=42) on row
#     indices + y, computed ONCE and reused for every modality subset below,
#     so every subset is evaluated on the identical 5 fold partitions --
#     same rigor as modality_ablation.py's single reused train_test_split,
#     extended to k folds.
#   - Same XGBoost hyperparameters as production: n_estimators=100,
#     max_depth=6, learning_rate=0.1, random_state=42. scale_pos_weight is
#     computed PER FOLD from that fold's own y_train (not once globally --
#     this is the one deliberate difference from modality_ablation.py's
#     single-split design, requested explicitly for this experiment).
#   - All seven modality subsets from the original ablation are re-run here
#     (full fusion vs CodeBERT-only is the priority pair; the rest complete
#     the confidence-interval version of that table).
#
# Run: python src/model/cross_validation.py
# =============================================================================

import json
import os
import time

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
FINAL_CSV = os.path.join(PROJECT_ROOT, "dataset", "processed", "final_features.csv")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results", "experiments")
OUT_JSON = os.path.join(RESULTS_DIR, "cross_validation.json")

N_SPLITS = 5
RANDOM_STATE = 42
N_ESTIMATORS = 100

# Copied verbatim from src/model/train_classifier.py / modality_ablation.py --
# do not let this list drift from those files' own definitions.
METADATA_COLS = ["sample_id", "target", "project", "commit_id", "func"]
MET_COL_NAMES = [
    "loc", "function_count", "loop_count", "if_count", "return_count",
    "avg_line_length", "max_line_length", "comment_count",
    "total_lines", "blank_lines", "nesting_depth", "operator_count", "pointer_count",
]


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
    feature_cols = [c for c in df.columns if c not in METADATA_COLS]

    ast_cols = [c for c in feature_cols if c.startswith("n_") or c == "max_depth"]
    met_cols = [c for c in feature_cols if c in MET_COL_NAMES]
    emb_cols = [c for c in feature_cols if c.startswith("embed_")]

    assert len(ast_cols) == 11 and len(met_cols) == 13 and len(emb_cols) == 768
    assert ast_cols + met_cols + emb_cols == feature_cols
    print("  PASS: 11 AST + 13 metrics + 768 CodeBERT = 792, same column identification "
          "logic as modality_ablation.py / train_classifier.py.")

    section(f"STRATIFIED {N_SPLITS}-FOLD SPLIT (row indices, reused for every modality subset)")
    idx = np.arange(len(df))
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    folds = list(skf.split(idx, y))
    for i, (tr, te) in enumerate(folds):
        n_safe_tr = int((y[tr] == 0).sum())
        n_vuln_tr = int((y[tr] == 1).sum())
        n_safe_te = int((y[te] == 0).sum())
        n_vuln_te = int((y[te] == 1).sum())
        print(f"  Fold {i}: train={len(tr)} (safe={n_safe_tr}, vuln={n_vuln_tr})  "
              f"test={len(te)} (safe={n_safe_te}, vuln={n_vuln_te})")

    # Sanity check: re-deriving the fold split a second, independent way must
    # produce identical fold assignments -- confirms reproducibility, same
    # spirit as modality_ablation.py's train_test_split repeat-call check.
    skf_check = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    folds_check = list(skf_check.split(idx, y))
    for (tr, te), (tr2, te2) in zip(folds, folds_check):
        assert np.array_equal(tr, tr2) and np.array_equal(te, te2), (
            "STOP: StratifiedKFold produced different fold assignments on a repeat call "
            "with identical arguments -- results would not be comparable across subsets."
        )
    print("  PASS: re-running StratifiedKFold with identical arguments reproduces the "
          "exact same fold assignments.")

    def run_subset_cv(name, cols):
        X = df[cols].values
        if np.isnan(X).sum() > 0:
            X = np.nan_to_num(X, nan=0.0)

        fold_metrics = []
        for fold_i, (tr, te) in enumerate(folds):
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

            fold_metrics.append({
                "fold": fold_i,
                "scale_pos_weight": scale_pos_weight,
                "accuracy": float(accuracy_score(y_test, y_pred)),
                "precision": float(precision_score(y_test, y_pred, zero_division=0)),
                "recall": float(recall_score(y_test, y_pred, zero_division=0)),
                "f1": float(f1_score(y_test, y_pred, zero_division=0)),
                "auc": float(roc_auc_score(y_test, y_proba)),
            })

        def mean_std(key):
            vals = np.array([m[key] for m in fold_metrics])
            return float(vals.mean()), float(vals.std(ddof=1)), float(vals.std(ddof=1) / np.sqrt(len(vals)))

        summary = {}
        for key in ("accuracy", "precision", "recall", "f1", "auc"):
            mean, std, se = mean_std(key)
            summary[key] = {"mean": round(mean, 4), "std": round(std, 4), "se": round(se, 4)}

        return {
            "name": name,
            "n_features": X.shape[1],
            "fold_metrics": fold_metrics,
            "summary": summary,
        }

    subsets = [
        ("Full fusion (AST + Metrics + CodeBERT)", feature_cols),
        ("CodeBERT only", emb_cols),
        ("AST only", ast_cols),
        ("Metrics only", met_cols),
        ("AST + Metrics (no CodeBERT)", ast_cols + met_cols),
        ("CodeBERT + AST (no metrics)", ast_cols + emb_cols),
        ("CodeBERT + Metrics (no AST)", met_cols + emb_cols),
    ]

    section(f"RUNNING {N_SPLITS}-FOLD CV ON EACH MODALITY SUBSET")
    results = []
    for name, cols in subsets:
        t0 = time.time()
        print(f"\n  {name} ({len(cols)} features) -- {N_SPLITS} folds...")
        r = run_subset_cv(name, cols)
        results.append(r)
        s = r["summary"]
        print(f"    F1  = {s['f1']['mean']:.4f} +/- {s['f1']['std']:.4f}  (SE={s['f1']['se']:.4f})")
        print(f"    AUC = {s['auc']['mean']:.4f} +/- {s['auc']['std']:.4f}  (SE={s['auc']['se']:.4f})")
        print(f"    ({time.time() - t0:.1f}s)")

    section("SUMMARY TABLE (mean +/- std across 5 folds)")
    header = f"  {'Subset':<40} {'#Feat':>6} {'F1':>16} {'AUC':>16} {'Precision':>16} {'Recall':>16}"
    print(f"\n{header}")
    print(f"  {'-'*len(header)}")
    for r in results:
        s = r["summary"]
        print(f"  {r['name']:<40} {r['n_features']:>6} "
              f"{s['f1']['mean']:>7.4f}+/-{s['f1']['std']:<6.4f} "
              f"{s['auc']['mean']:>7.4f}+/-{s['auc']['std']:<6.4f} "
              f"{s['precision']['mean']:>7.4f}+/-{s['precision']['std']:<6.4f} "
              f"{s['recall']['mean']:>7.4f}+/-{s['recall']['std']:<6.4f}")

    section("PRIORITY COMPARISON: Full fusion vs. CodeBERT-only")
    full = next(r for r in results if r["name"].startswith("Full fusion"))
    cb = next(r for r in results if r["name"] == "CodeBERT only")
    f1_full, f1_cb = full["summary"]["f1"]["mean"], cb["summary"]["f1"]["mean"]
    se_full, se_cb = full["summary"]["f1"]["se"], cb["summary"]["f1"]["se"]
    diff = f1_full - f1_cb
    combined_se = float(np.sqrt(se_full ** 2 + se_cb ** 2))
    print(f"  Full fusion F1: {f1_full:.4f} +/- {se_full:.4f} (SE)")
    print(f"  CodeBERT-only F1: {f1_cb:.4f} +/- {se_cb:.4f} (SE)")
    print(f"  Difference (full - CodeBERT-only): {diff:+.4f}")
    print(f"  Combined SE: {combined_se:.4f}  ->  difference / combined SE = {diff / combined_se:+.2f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "n_splits": N_SPLITS,
            "random_state": RANDOM_STATE,
            "n_estimators": N_ESTIMATORS,
            "n_rows": int(len(df)),
            "column_groups": {"ast": ast_cols, "metrics": met_cols, "codebert_count": len(emb_cols)},
            "results": results,
            "priority_comparison": {
                "full_fusion_f1_mean": f1_full,
                "full_fusion_f1_se": se_full,
                "codebert_only_f1_mean": f1_cb,
                "codebert_only_f1_se": se_cb,
                "difference": round(diff, 4),
                "combined_se": round(combined_se, 4),
                "diff_over_combined_se": round(diff / combined_se, 4),
            },
        }, f, indent=2)
    print(f"\n  Results saved: {OUT_JSON}")
    print(f"  Total runtime: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
