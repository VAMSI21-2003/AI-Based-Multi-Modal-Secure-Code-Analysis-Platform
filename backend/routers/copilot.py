# =============================================================================
# routers/copilot.py -- AI Security Copilot endpoint.
# =============================================================================

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

import copilot
from database import get_db

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


class AskRequest(BaseModel):
    question: str
    scan_id: str | None = None


@router.post("/ask")
def ask(req: AskRequest, db: Session = Depends(get_db)):
    return copilot.answer(req.question, req.scan_id, db)
