# =============================================================================
# scan_service.py -- core scan orchestration shared by the single-file and
# batch endpoints. Wraps ml_bridge.run_prediction() (the existing trained
# pipeline) and persists results to SQLite for history/dashboard/analytics.
# =============================================================================

import json
import datetime as dt

from sqlalchemy.orm import Session

import ml_bridge
from database import ScanRecord, new_id


def run_and_store_scan(
    db: Session,
    code: str,
    project_name: str,
    filename: str,
    model_choice: str,
    source: str,
    batch_id: str = None,
) -> ScanRecord:
    result = ml_bridge.run_prediction(code, model_choice)

    ast_feats = result.get("ast_features", {})
    metric_feats = result.get("metric_features", {})

    # Project this sample's embedding onto the precomputed 2D PCA space
    # (visualisation only). We recompute the embedding cheaply by rerunning
    # feature extraction is wasteful, so pull it from result if present.
    emb_xy = (None, None)
    tokenizer_available = not result.get("is_demo", True)
    if tokenizer_available:
        try:
            _, embedding = ml_bridge.full_feature_vector(code, ast_feats, metric_feats)
            projected = ml_bridge.project_embedding(embedding)
            if projected:
                emb_xy = (projected[0], projected[1])
        except Exception:
            pass

    record = ScanRecord(
        id=new_id(),
        batch_id=batch_id,
        project_name=project_name or "Untitled Project",
        filename=filename or "pasted_code.c",
        source=source or "paste",
        code=code,
        verdict=result["verdict"],
        vuln_probability=result["vuln_probability"],
        safe_probability=result["safe_probability"],
        confidence=result["confidence"],
        risk_level=result["risk_level"],
        risk_tag=result["risk_tag"],
        risk_color=result["risk_color"],
        model_used=result["model_used"],
        is_demo=1 if result.get("is_demo") else 0,
        ast_features_json=json.dumps(ast_feats),
        metric_features_json=json.dumps(metric_feats),
        embedding_dims=result.get("embedding_dims", 0),
        embedding_2d_x=emb_xy[0],
        embedding_2d_y=emb_xy[1],
        lines=len(code.split("\n")),
        loc=metric_feats.get("loc", 0),
        created_at=dt.datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def record_to_dict(r: ScanRecord, include_code: bool = True) -> dict:
    d = {
        "id": r.id,
        "batch_id": r.batch_id,
        "project_name": r.project_name,
        "filename": r.filename,
        "source": r.source,
        "verdict": r.verdict,
        "vuln_probability": r.vuln_probability,
        "safe_probability": r.safe_probability,
        "confidence": r.confidence,
        "risk_level": r.risk_level,
        "risk_tag": r.risk_tag,
        "risk_color": r.risk_color,
        "model_used": r.model_used,
        "is_demo": bool(r.is_demo),
        "ast_features": json.loads(r.ast_features_json or "{}"),
        "metric_features": json.loads(r.metric_features_json or "{}"),
        "embedding_dims": r.embedding_dims,
        "embedding_2d": (
            {"x": r.embedding_2d_x, "y": r.embedding_2d_y}
            if r.embedding_2d_x is not None else None
        ),
        "lines": r.lines,
        "loc": r.loc,
        "is_pinned": bool(r.is_pinned),
        "tags": [t for t in (r.tags or "").split(",") if t],
        "created_at": r.created_at.isoformat() + "Z",
    }
    if include_code:
        d["code"] = r.code
        # Additive cross-check only, computed on-demand from the same
        # regex heuristic already used for line-level highlighting -- never
        # persisted, never fed back into the stored ML verdict above.
        d["evidence_risk"] = ml_bridge.evidence_based_risk(r.risk_level, ml_bridge.line_risk_scan(r.code))
    return d
