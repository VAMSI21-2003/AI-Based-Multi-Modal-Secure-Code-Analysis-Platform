# =============================================================================
# routers/history.py -- Scan History module: search, filter, sort, export.
# =============================================================================

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db, ScanRecord
from scan_service import record_to_dict

router = APIRouter(prefix="/api/history", tags=["history"])

SORT_FIELDS = {
    "date": ScanRecord.created_at,
    "risk": ScanRecord.vuln_probability,
    "confidence": ScanRecord.confidence,
    "filename": ScanRecord.filename,
}


def _apply_filters(query, search, risk_level, project, verdict, source, pinned=None, tag=None):
    if search:
        like = f"%{search}%"
        query = query.filter(or_(ScanRecord.filename.ilike(like), ScanRecord.project_name.ilike(like)))
    if risk_level:
        query = query.filter(ScanRecord.risk_level == risk_level)
    if project:
        query = query.filter(ScanRecord.project_name == project)
    if verdict:
        query = query.filter(ScanRecord.verdict == verdict)
    if source:
        query = query.filter(ScanRecord.source == source)
    if pinned is not None:
        query = query.filter(ScanRecord.is_pinned == (1 if pinned else 0))
    if tag:
        query = query.filter(ScanRecord.tags.ilike(f"%{tag}%"))
    return query


@router.get("")
def list_history(
    search: str = Query(None),
    risk_level: str = Query(None),
    project: str = Query(None),
    verdict: str = Query(None),
    source: str = Query(None),
    pinned: bool = Query(None),
    tag: str = Query(None),
    sort: str = Query("date"),
    order: str = Query("desc"),
    limit: int = Query(25, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    query = db.query(ScanRecord)
    query = _apply_filters(query, search, risk_level, project, verdict, source, pinned, tag)

    total = query.count()

    sort_col = SORT_FIELDS.get(sort, ScanRecord.created_at)
    sort_col = sort_col.desc() if order == "desc" else sort_col.asc()
    rows = query.order_by(sort_col).offset(offset).limit(limit).all()

    projects = [p[0] for p in db.query(ScanRecord.project_name).distinct().all()]
    all_tags = sorted({
        t for row in db.query(ScanRecord.tags).filter(ScanRecord.tags.isnot(None), ScanRecord.tags != "").all()
        for t in (row[0] or "").split(",") if t
    })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "projects": projects,
        "tags": all_tags,
        "results": [record_to_dict(r, include_code=False) for r in rows],
    }


class TagsRequest(BaseModel):
    tags: list[str]


@router.patch("/{scan_id}/pin")
def toggle_pin(scan_id: str, db: Session = Depends(get_db)):
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")
    record.is_pinned = 0 if record.is_pinned else 1
    db.commit()
    db.refresh(record)
    return {"id": record.id, "is_pinned": bool(record.is_pinned)}


@router.patch("/{scan_id}/tags")
def set_tags(scan_id: str, req: TagsRequest, db: Session = Depends(get_db)):
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")
    clean = sorted({t.strip() for t in req.tags if t.strip()})
    record.tags = ",".join(clean)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "tags": clean}


@router.get("/pinned")
def list_pinned(db: Session = Depends(get_db)):
    rows = db.query(ScanRecord).filter(ScanRecord.is_pinned == 1).order_by(ScanRecord.created_at.desc()).all()
    return {"results": [record_to_dict(r, include_code=False) for r in rows]}


@router.get("/export")
def export_history(
    format: str = Query("json", pattern="^(json|csv)$"),
    search: str = Query(None),
    risk_level: str = Query(None),
    project: str = Query(None),
    verdict: str = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(ScanRecord)
    query = _apply_filters(query, search, risk_level, project, verdict, None)
    rows = query.order_by(ScanRecord.created_at.desc()).all()
    data = [record_to_dict(r, include_code=False) for r in rows]

    if format == "json":
        buf = io.StringIO(json.dumps(data, indent=2))
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=scan_history.json"},
        )

    # CSV
    buf = io.StringIO()
    fieldnames = [
        "id", "project_name", "filename", "source", "verdict", "vuln_probability",
        "confidence", "risk_level", "model_used", "loc", "lines", "created_at",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in data:
        writer.writerow(row)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=scan_history.csv"},
    )
