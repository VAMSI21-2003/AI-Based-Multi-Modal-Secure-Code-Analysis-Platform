# =============================================================================
# routers/research.py -- Research page data: model architecture facts,
# real confusion matrix / ROC / PR curves (precomputed, read-only
# evaluation -- see precompute_eval_curves.py), and parameter counts.
# Purely additive; does not touch the trained models or training pipeline.
# =============================================================================

import os
import json
import functools

from fastapi import APIRouter

import ml_bridge

router = APIRouter(prefix="/api/research", tags=["research"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVAL_CURVES_PATH = os.path.join(PROJECT_ROOT, "backend", "data", "eval_curves.json")
TRAINING_METADATA_PATH = os.path.join(PROJECT_ROOT, "models", "training_metadata.json")


@functools.lru_cache(maxsize=1)
def _eval_curves():
    if not os.path.exists(EVAL_CURVES_PATH):
        return None
    with open(EVAL_CURVES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/eval-curves")
def eval_curves():
    data = _eval_curves()
    if data is None:
        return {"available": False}
    return {"available": True, **data}


@router.get("/architecture")
def model_architecture():
    xgb = ml_bridge.get_xgb_model()
    rf = ml_bridge.get_rf_model()

    xgb_info = None
    if xgb is not None:
        booster = xgb.get_booster()
        # xgb.n_estimators / .max_depth / .learning_rate are sklearn-wrapper
        # constructor params -- load_model() restores the booster's trees
        # but not these attributes, so read the real values back out of the
        # booster's own saved config instead.
        try:
            cfg = json.loads(booster.save_config())
            train_params = cfg.get("learner", {}).get("gradient_booster", {}).get("tree_train_param", {})
            max_depth = int(train_params.get("max_depth")) if train_params.get("max_depth") else None
            learning_rate = float(train_params.get("eta")) if train_params.get("eta") else None
        except Exception:
            max_depth, learning_rate = None, None
        xgb_info = {
            "n_estimators": len(booster.get_dump()),
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "total_trees": len(booster.get_dump()),
        }

    rf_info = None
    if rf is not None:
        total_nodes = sum(t.tree_.node_count for t in rf.estimators_)
        rf_info = {
            "n_estimators": rf.n_estimators,
            "max_depth": rf.max_depth,
            "total_trees": len(rf.estimators_),
            "total_nodes": int(total_nodes),
        }

    codebert_params = None
    tokenizer, codebert_model = ml_bridge.get_codebert()
    if codebert_model is not None:
        codebert_params = sum(p.numel() for p in codebert_model.parameters())

    training_meta = None
    if os.path.exists(TRAINING_METADATA_PATH):
        with open(TRAINING_METADATA_PATH, "r", encoding="utf-8") as f:
            training_meta = json.load(f)

    return {
        "codebert": {
            "model_name": "microsoft/codebert-base",
            "parameters": codebert_params,
            "layers": 12,
            "hidden_size": 768,
            "attention_heads": 12,
            "max_sequence_length": 512,
        },
        "xgboost": xgb_info,
        "random_forest": rf_info,
        "feature_pipeline": {
            "ast_dimensions": 11,
            "metrics_dimensions": 13,
            "embedding_dimensions": 768,
            "total_dimensions": 792,
        },
        "training": training_meta,
    }
