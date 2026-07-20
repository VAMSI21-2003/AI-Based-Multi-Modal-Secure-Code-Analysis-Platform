# =============================================================================
# routers/gamification.py -- Security Gamification endpoint (Phase 3, #17).
# =============================================================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import gamification
from database import get_db

router = APIRouter(prefix="/api/gamification", tags=["gamification"])


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return gamification.compute_status(db)
