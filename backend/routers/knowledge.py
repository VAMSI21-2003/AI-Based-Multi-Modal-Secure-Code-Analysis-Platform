# =============================================================================
# routers/knowledge.py -- Vulnerability Knowledge Base module.
# =============================================================================

from fastapi import APIRouter, HTTPException

import knowledge_base

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("")
def list_knowledge():
    return {"entries": knowledge_base.all_entries()}


@router.get("/{cwe_id}")
def get_knowledge(cwe_id: str):
    entry = knowledge_base.lookup(cwe_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Unknown CWE")
    return entry
