# =============================================================================
# routers/patches.py -- AI Auto Patch Generator endpoint.
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import auto_patch
from database import get_db, ScanRecord

router = APIRouter(prefix="/api/scan", tags=["patches"])


@router.get("/{scan_id}/patches")
def get_patches(scan_id: str, db: Session = Depends(get_db)):
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")
    return auto_patch.generate_patches(record.code)
