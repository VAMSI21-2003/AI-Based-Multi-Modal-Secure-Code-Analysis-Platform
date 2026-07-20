# =============================================================================
# routers/search.py -- Vulnerability Search Engine endpoint (Phase 3, #18).
# =============================================================================

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import search_service
from database import get_db

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search(
    q: str = Query(...),
    category: str = Query("all", pattern="^(all|cwe|api|function|variable|pointer|loop|risk)$"),
    db: Session = Depends(get_db),
):
    return search_service.search(db, q, category)
