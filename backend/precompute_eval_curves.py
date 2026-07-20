# =============================================================================
# precompute_eval_curves.py -- one-time, READ-ONLY evaluation script.
#
# Reproduces the EXACT train/test split used by src/model/train_classifier.py
# (same feature columns, same test_size=0.20, same random_state=42, same
# stratify=y) so the test set is bit-for-bit identical to what the models
# were originally evaluated on. It then loads the ALREADY-TRAINED models
# (models/xgboost.json, models/random_forest.joblib) and calls .predict() /
# .predict_proba() on the test set -- ZERO fitting, zero weight changes.
#
# This is evaluation, not training: it derives confusion matrices, ROC
# curves, and PR curves for the Research page from real data, instead of
# fabricating placeholder numbers.
#
# Run once:  python backend/precompute_eval_curves.py
# Output:    backend/data/eval_curves.json
# =============================================================================

import os
import sys
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    confusion_matrix, roc_curve, auc, precision_recall_curve,
    accuracy_score, precision_score, recall_score, f1_score,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL_FEATURES_PATH = os.path.join(PROJECT_ROOT, "dataset", "processed", "final_features.csv")
XGB_MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "xgboost.json")
RF_MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "random_forest.joblib")
OUT_PATH = os.path.join(PROJECT_ROOT, "backend", "data", "eval_curves.json")

APP_DIR = os.path.join(PROJECT_ROOT, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
from utils import AST_FEATURE_COLS, METRICS_FEATURE_COLS  # noqa: E402 -- existing, unmodified column lists

METADATA_COLS = ["sample_id", "target", "project", "commit_id"]  # must match train_classifier.py exactly
TEST_SIZE = 0.20
RANDOM_STATE = 42
CURVE_POINTS = 60  # downsample curves to a manageable number of points for the frontend


def _downsample(x, y, n=CURVE_POINTS):
    if len(x) <= n:
        return list(x), list(y)
    idx = np.linspace(0, len(x) - 1, n).astype(int)
    return [round(float(x[i]), 4) for i in idx], [round(float(y[i]), 4) for i in idx]


def main():
    print("Loading final_features.csv (existing, unmodified)...")
    df = pd.read_csv(FINAL_FEATURES_PATH)
    y = df["target"].values
    feature_cols = [c for c in df.columns if c not in METADATA_COLS]
    X = df[feature_cols].values
    print(f"  {len(df)} samples, {len(feature_cols)} features")

    print("Reproducing the exact original train/test split (random_state=42, stratify=y)...")
    _, X_test, _, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y,
    )
    print(f"  Test set: {len(X_test)} samples")

    results = {}

    if os.path.exists(XGB_MODEL_PATH):
        from xgboost import XGBClassifier
        print("Evaluating existing XGBoost model (no fitting)...")
        model = XGBClassifier(verbosity=0)
        model.load_model(XGB_MODEL_PATH)
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        results["xgboost"] = _evaluate(y_test, y_pred, y_proba)
        results["xgboost"]["feature_importances_top20"] = _top_importances(model, feature_cols)
        results["xgboost"]["ablation"] = _ablation_study(model, X_test, y_test, feature_cols)

    if os.path.exists(RF_MODEL_PATH):
        import joblib
        print("Evaluating existing Random Forest model (no fitting)...")
        model = joblib.load(RF_MODEL_PATH)
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        results["random_forest"] = _evaluate(y_test, y_pred, y_proba)
        results["random_forest"]["feature_importances_top20"] = _top_importances(model, feature_cols)
        results["random_forest"]["ablation"] = _ablation_study(model, X_test, y_test, feature_cols)

    results["test_set_size"] = int(len(X_test))
    results["test_set_vulnerable"] = int((y_test == 1).sum())
    results["test_set_safe"] = int((y_test == 0).sum())

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f)
    print(f"Saved: {OUT_PATH}")


def _evaluate(y_test, y_pred, y_proba):
    cm = confusion_matrix(y_test, y_pred, labels=[0, 1])
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    roc_auc = auc(fpr, tpr)
    prec, rec, _ = precision_recall_curve(y_test, y_proba)

    fpr_ds, tpr_ds = _downsample(fpr, tpr)
    rec_ds, prec_ds = _downsample(rec, prec)

    return {
        "confusion_matrix": {
            "tn": int(cm[0, 0]), "fp": int(cm[0, 1]), "fn": int(cm[1, 0]), "tp": int(cm[1, 1]),
        },
        "roc_curve": {"fpr": fpr_ds, "tpr": tpr_ds, "auc": round(float(roc_auc), 4)},
        "pr_curve": {"recall": rec_ds, "precision": prec_ds},
    }


def _ablation_study(model, X_test, y_test, feature_cols):
    """
    Feature-block ablation via INPUT MASKING at inference time -- zeroes out
    whole feature blocks (AST / Metrics / CodeBERT embedding) on a COPY of
    the test set and re-runs .predict()/.predict_proba() on the SAME
    already-trained model. No fitting occurs; the model's weights are never
    touched. This measures how much each modality contributes to the
    existing model's decisions, without training separate single-modality
    models (which the project's fixed pipeline does not have).
    """
    idx = {name: i for i, name in enumerate(feature_cols)}
    ast_idx = [idx[c] for c in AST_FEATURE_COLS if c in idx]
    metrics_idx = [idx[c] for c in METRICS_FEATURE_COLS if c in idx]
    all_idx = set(range(len(feature_cols)))
    embed_idx = sorted(all_idx - set(ast_idx) - set(metrics_idx))

    configs = {
        "Full (AST + Metrics + CodeBERT)": [],
        "AST only": metrics_idx + embed_idx,
        "Metrics only": ast_idx + embed_idx,
        "CodeBERT only": ast_idx + metrics_idx,
        "AST + Metrics (no CodeBERT)": embed_idx,
    }

    results = []
    for label, zero_cols in configs.items():
        X_masked = X_test.copy()
        if zero_cols:
            X_masked[:, zero_cols] = 0
        y_pred = model.predict(X_masked)
        results.append({
            "config": label,
            "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
            "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        })
    return results


def _top_importances(model, feature_cols, n=20):
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        return []
    order = np.argsort(-importances)[:n]
    return [{"feature": feature_cols[i], "importance": round(float(importances[i]), 5)} for i in order]


if __name__ == "__main__":
    main()
