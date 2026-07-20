# =============================================================================
# routers/comparison.py -- Model Comparison ("Random Forest vs XGBoost").
#
# Purely additive: a new, isolated endpoint. Does not modify scan.py or any
# existing route. Reruns BOTH already-trained models (unchanged weights)
# against the same stored source code so their predictions can be compared
# side by side. No retraining, no DB schema changes -- computed on demand,
# same pattern as /detail and /intelligence.
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import ml_bridge
from database import get_db, ScanRecord
from scan_service import record_to_dict

router = APIRouter(prefix="/api/scan", tags=["comparison"])


def _run_one(model, X):
    if model is None:
        return None
    pred = int(model.predict(X)[0])
    proba = model.predict_proba(X)[0]
    vuln_prob = float(proba[1])
    confidence = vuln_prob if pred == 1 else (1.0 - vuln_prob)
    return {
        "available": True,
        "verdict": "VULNERABLE" if pred == 1 else "NOT VULNERABLE",
        "vuln_probability": round(vuln_prob * 100, 2),
        "safe_probability": round((1.0 - vuln_prob) * 100, 2),
        "confidence": round(confidence * 100, 2),
    }


@router.get("/{scan_id}/model-comparison")
def model_comparison(scan_id: str, db: Session = Depends(get_db)):
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")

    if record.is_demo:
        return {
            "available": False,
            "error": "This scan ran in demo mode (no trained models were available at scan time).",
            "xgboost": None, "random_forest": None, "agreement": None, "probability_diff": None,
        }

    d = record_to_dict(record)
    try:
        feature_vector, _ = ml_bridge.full_feature_vector(record.code, d["ast_features"], d["metric_features"])
    except Exception as e:
        return {"available": False, "error": str(e), "xgboost": None, "random_forest": None, "agreement": None, "probability_diff": None}

    X = feature_vector.reshape(1, -1)

    xgb_model = ml_bridge.get_xgb_model()
    rf_model = ml_bridge.get_rf_model()

    xgb_result = _run_one(xgb_model, X)
    rf_result = _run_one(rf_model, X)

    agreement = None
    prob_diff = None
    if xgb_result and rf_result:
        agreement = xgb_result["verdict"] == rf_result["verdict"]
        prob_diff = round(abs(xgb_result["vuln_probability"] - rf_result["vuln_probability"]), 2)

    return {
        "available": True,
        "xgboost": xgb_result or {"available": False},
        "random_forest": rf_result or {"available": False},
        "agreement": agreement,
        "probability_diff": prob_diff,
    }
