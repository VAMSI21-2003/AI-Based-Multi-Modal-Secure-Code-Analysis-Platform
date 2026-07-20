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
