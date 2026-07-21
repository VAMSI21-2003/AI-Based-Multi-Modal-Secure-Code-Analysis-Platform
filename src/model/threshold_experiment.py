# =============================================================================
# threshold_experiment.py -- Phase 5 experiment: threshold optimization.
#
# Methodology (must not be violated):
#   1. Recreate the EXACT SAME train_test_split (random_state=42, test_size=0.2,
#      stratify=y) that produced the production model's test set -- this test
#      set is treated as untouched ground truth, evaluated ONCE at the end.
#   2. Carve a validation set OUT OF THE TRAINING PORTION ONLY (never touches
#      the test set). A fresh model is trained on the remaining training data.
#   3. Sweep decision thresholds on the VALIDATION set only, pick the
#      F1-maximizing threshold.
#   4. Apply that ONE chosen threshold to the untouched test set exactly once.
#
# This does NOT overwrite models/xgboost.json (the production artifact) --
# results are written to results/experiments/ only.
# =============================================================================

import os
import json

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score, roc_auc_score
from xgboost import XGBClassifier

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FINAL_CSV = os.path.join(PROJECT_ROOT, "dataset", "processed", "final_features.csv")
OUT_DIR = os.path.join(PROJECT_ROOT, "results", "experiments")
os.makedirs(OUT_DIR, exist_ok=True)

METADATA_COLS = ["sample_id", "target", "project", "commit_id", "func"]
TEST_SIZE = 0.20
RANDOM_STATE = 42


def main():
    df = pd.read_csv(FINAL_CSV)
    y = df["target"].values
    feature_cols = [c for c in df.columns if c not in METADATA_COLS]
    X = df[feature_cols].values
    X = np.nan_to_num(X, nan=0.0)

    # Step 1: EXACT reproduction of the production train/test split.
    X_trainfull, X_test, y_trainfull, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y,
    )

    # Step 2: carve a validation set out of the TRAINING portion only.
    # test set above is never touched again until the very last step.
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainfull, y_trainfull, test_size=0.20, random_state=RANDOM_STATE, stratify=y_trainfull,
    )

    print(f"train={len(X_train)} val={len(X_val)} test={len(X_test)} (test set identical to production's)")

    n_safe, n_vuln = int((y_train == 0).sum()), int((y_train == 1).sum())
    scale_pos_weight = round(n_safe / max(n_vuln, 1), 2)

    model = XGBClassifier(
        n_estimators=100, max_depth=6, learning_rate=0.1,
        scale_pos_weight=scale_pos_weight, random_state=RANDOM_STATE, verbosity=0,
    )
    model.fit(X_train, y_train)

    # Step 3: sweep thresholds on VALIDATION ONLY.
    val_proba = model.predict_proba(X_val)[:, 1]
    thresholds = np.arange(0.05, 0.96, 0.01)
    sweep = []
    for t in thresholds:
        pred = (val_proba >= t).astype(int)
        sweep.append({
            "threshold": round(float(t), 2),
            "precision": round(float(precision_score(y_val, pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_val, pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_val, pred, zero_division=0)), 4),
        })
    best = max(sweep, key=lambda r: r["f1"])
    best_threshold = best["threshold"]
    print(f"Best threshold on VALIDATION set (by F1): {best_threshold} (val F1={best['f1']})")

    # Baseline: default 0.5 threshold on validation, for comparison.
    default_val_pred = (val_proba >= 0.5).astype(int)
    default_val_f1 = round(float(f1_score(y_val, default_val_pred, zero_division=0)), 4)

    # Step 4: apply chosen threshold to the UNTOUCHED test set, exactly once.
    test_proba = model.predict_proba(X_test)[:, 1]

    def eval_at(threshold):
        pred = (test_proba >= threshold).astype(int)
        return {
            "threshold": threshold,
            "accuracy": round(float(accuracy_score(y_test, pred)), 4),
            "precision": round(float(precision_score(y_test, pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, pred, zero_division=0)), 4),
            "auc": round(float(roc_auc_score(y_test, test_proba)), 4),
        }

    test_at_default = eval_at(0.5)
    test_at_tuned = eval_at(best_threshold)

    result = {
        "methodology": "train/val/test split; threshold chosen on validation only; test evaluated once",
        "split_sizes": {"train": len(X_train), "val": len(X_val), "test": len(X_test)},
        "val_threshold_sweep": sweep,
        "best_threshold_by_val_f1": best_threshold,
        "val_f1_at_default_0.5": default_val_f1,
        "val_f1_at_best_threshold": best["f1"],
        "test_at_default_threshold_0.5": test_at_default,
        "test_at_tuned_threshold": test_at_tuned,
        "note": (
            "This experiment retrains a NEW XGBoost model (same hyperparameters as production) "
            "on a train subset with a carved-out validation set, so it is NOT numerically "
            "identical to the production model trained on the full training portion -- expect "
            "small differences from models/training_metadata.json due to the smaller training set."
        ),
    }

    out_path = os.path.join(OUT_DIR, "threshold_experiment.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved: {out_path}")
    print(f"\nTest @ default 0.5: {test_at_default}")
    print(f"Test @ tuned {best_threshold}: {test_at_tuned}")


if __name__ == "__main__":
    main()
