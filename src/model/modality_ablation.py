# =============================================================================
# modality_ablation.py -- modality ablation over the ALREADY-FUSED,
# ALREADY-ALIGNMENT-FIXED feature table (dataset/processed/final_features.csv).
#
# This script does NOT touch extraction, fusion_core.py, or the alignment
# logic in any way -- it only reads the existing fused CSV and column-slices
# it. It exists to answer one question: on the corrected dataset, does
# multi-modal fusion actually beat the best single modality, and by how much?
#
# Methodology (must match src/model/train_classifier.py's current production
# baseline EXACTLY, or the comparison is invalid):
#   - Same METADATA_COLS exclusion, same AST/metrics/CodeBERT column
#     identification logic (copied verbatim from train_classifier.py, not
#     reimplemented differently).
#   - ONE train_test_split call on row indices (test_size=0.20,
#     random_state=42, stratify=y) -- the resulting indices are reused for
#     EVERY modality subset below, so every subset trains/tests on the
#     identical set of rows. This is stronger than calling train_test_split
#     separately per subset (which would also be deterministic here, but
#     capturing indices once and slicing removes any doubt).
#   - Same XGBoost hyperparameters as train_classifier.py's production
#     model: n_estimators=100, max_depth=6, learning_rate=0.1,
#     scale_pos_weight computed from the (identical, per above) y_train,
#     random_state=42.
#
# Run: python src/model/modality_ablation.py
# =============================================================================

import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
FINAL_CSV = os.path.join(PROJECT_ROOT, "dataset", "processed", "final_features.csv")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results", "experiments")
OUT_JSON = os.path.join(RESULTS_DIR, "modality_ablation.json")

TEST_SIZE = 0.20
RANDOM_STATE = 42
N_ESTIMATORS = 100

# Copied verbatim from src/model/train_classifier.py -- do not let this list
# drift from that file's own definition, since a mismatch here would make
# "same baseline" claims false.
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
    section("LOAD final_features.csv (already fused, already alignment-fixed)")
    df = pd.read_csv(FINAL_CSV, encoding="utf-8")
    print(f"  Rows   : {len(df)}")
    print(f"  Columns: {len(df.columns)}")

    y = df["target"].values
    feature_cols = [c for c in df.columns if c not in METADATA_COLS]

    ast_cols = [c for c in feature_cols if c.startswith("n_") or c == "max_depth"]
    met_cols = [c for c in feature_cols if c in MET_COL_NAMES]
    emb_cols = [c for c in feature_cols if c.startswith("embed_")]

    section("CONFIRM COLUMN BOUNDARIES")
    print(f"  AST columns     ({len(ast_cols)}): {ast_cols}")
    print(f"  Metrics columns ({len(met_cols)}): {met_cols}")
    print(f"  CodeBERT columns({len(emb_cols)}): {emb_cols[0]} .. {emb_cols[-1]}")
    assert len(ast_cols) == 11, f"expected 11 AST columns, got {len(ast_cols)}"
    assert len(met_cols) == 13, f"expected 13 metrics columns, got {len(met_cols)}"
    assert len(emb_cols) == 768, f"expected 768 CodeBERT columns, got {len(emb_cols)}"
    assert ast_cols + met_cols + emb_cols == feature_cols, (
        "AST+metrics+CodeBERT column groups do not reconstruct feature_cols in the "
        "same order train_classifier.py uses -- STOP, something has drifted."
    )
    print("  PASS: 11 AST + 13 metrics + 768 CodeBERT = 792, contiguous, in the exact "
          "order train_classifier.py's own X = df[feature_cols].values uses.")

    section("SINGLE TRAIN/TEST SPLIT (reused for every modality subset)")
    idx = np.arange(len(df))
    idx_train, idx_test, y_train, y_test = train_test_split(
        idx, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y,
    )
    print(f"  test_size={TEST_SIZE}, random_state={RANDOM_STATE}, stratify=y")
    print(f"  Train: {len(idx_train)} rows (safe={int((y_train == 0).sum())}, vuln={int((y_train == 1).sum())})")
    print(f"  Test : {len(idx_test)} rows (safe={int((y_test == 0).sum())}, vuln={int((y_test == 1).sum())})")

    # Sanity check: re-deriving the split a second, independent way (calling
    # train_test_split again with the same arguments) must produce identical
    # indices -- confirms the split is not silently non-deterministic.
    idx_check_train, idx_check_test, _, _ = train_test_split(
        idx, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y,
    )
    assert np.array_equal(idx_train, idx_check_train) and np.array_equal(idx_test, idx_check_test), (
        "STOP: train_test_split produced different indices on a repeat call with "
        "identical arguments -- the split is not reproducible, ablation results "
        "would not be comparable."
    )
    print("  PASS: re-running train_test_split with identical arguments reproduces "
          "the exact same row indices.")

    n_safe_train = int((y_train == 0).sum())
    n_vuln_train = int((y_train == 1).sum())
    scale_pos_weight = round(n_safe_train / max(n_vuln_train, 1), 2)
    print(f"  scale_pos_weight (from y_train, identical for every subset below): {scale_pos_weight}")

    def run_subset(name, cols):
        X = df[cols].values
        if np.isnan(X).sum() > 0:
            X = np.nan_to_num(X, nan=0.0)
        X_train, X_test = X[idx_train], X[idx_test]

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
            "name": name,
            "n_features": X.shape[1],
            "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
            "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
            "auc": round(float(roc_auc_score(y_test, y_proba)), 4),
            "confusion_matrix": confusion_matrix(y_test, y_pred, labels=[0, 1]).tolist(),
        }

    subsets = [
        ("CodeBERT only", emb_cols),
        ("AST only", ast_cols),
        ("Metrics only", met_cols),
        ("AST + Metrics (no CodeBERT)", ast_cols + met_cols),
        ("CodeBERT + AST (no metrics)", ast_cols + emb_cols),
        ("CodeBERT + Metrics (no AST)", met_cols + emb_cols),
        ("Full fusion (AST + Metrics + CodeBERT)", feature_cols),
    ]

    section("TRAINING XGBOOST ON EACH MODALITY SUBSET")
    results = []
    for name, cols in subsets:
        print(f"\n  Training: {name} ({len(cols)} features)...")
        r = run_subset(name, cols)
        results.append(r)
        print(f"    Accuracy={r['accuracy']:.4f}  Precision={r['precision']:.4f}  "
              f"Recall={r['recall']:.4f}  F1={r['f1']:.4f}  AUC={r['auc']:.4f}")

    section("SUMMARY TABLE")
    print(f"\n  {'Subset':<40} {'#Feat':>6} {'Acc':>7} {'Prec':>7} {'Rec':>7} {'F1':>7} {'AUC':>7}")
    print(f"  {'-'*90}")
    for r in results:
        print(f"  {r['name']:<40} {r['n_features']:>6} {r['accuracy']:>7.4f} "
              f"{r['precision']:>7.4f} {r['recall']:>7.4f} {r['f1']:>7.4f} {r['auc']:>7.4f}")

    full = next(r for r in results if r["name"].startswith("Full fusion"))
    print(f"\n  Full-fusion F1 = {full['f1']:.4f} -- compare against the production baseline "
          f"(models/training_metadata.json xgboost.f1) to confirm this reproduces it.")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "test_size": TEST_SIZE,
            "random_state": RANDOM_STATE,
            "n_estimators": N_ESTIMATORS,
            "scale_pos_weight": scale_pos_weight,
            "n_train": int(len(idx_train)),
            "n_test": int(len(idx_test)),
            "column_groups": {"ast": ast_cols, "metrics": met_cols, "codebert_count": len(emb_cols)},
            "results": results,
        }, f, indent=2)
    print(f"\n  Results saved: {OUT_JSON}")


if __name__ == "__main__":
    main()
