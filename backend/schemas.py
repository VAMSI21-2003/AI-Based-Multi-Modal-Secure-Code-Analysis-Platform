# =============================================================================
# schemas.py -- Pydantic request models for the API.
# =============================================================================

from typing import Optional
from pydantic import BaseModel


class CodeScanRequest(BaseModel):
    code: str
    project_name: Optional[str] = "Untitled Project"
    filename: Optional[str] = "pasted_code.c"
    model_choice: Optional[str] = "XGBoost"
    source: Optional[str] = "paste"


class RewriteRequest(BaseModel):
    code: str


class LiveScanRequest(BaseModel):
    code: str
    model_choice: Optional[str] = "XGBoost"


class ApplyPatchRequest(BaseModel):
    # Purely informational -- identifies which AutoPatch.tsx card triggered
    # the action, for the response/UI's own reference. NOT used to select
    # what gets applied or to decide the safety check: the server always
    # recomputes recommendations.suggest_secure_rewrite() itself from the
    # scan's own stored, trusted code (see routers/patches.py) rather than
    # trusting client-supplied "already fixed" code for a safety-critical
    # decision -- see docs/APPLY_PATCH_LOOP_DESIGN.md Implementation notes.
    patch_id: Optional[str] = None
