# =============================================================================
# routers/patches.py -- AI Auto Patch Generator endpoint, plus the
# Apply-Patch -> Re-Scan loop (docs/APPLY_PATCH_LOOP_DESIGN.md).
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import auto_patch
import patch_safety
import recommendations
from database import get_db, ScanRecord
from schemas import ApplyPatchRequest
from scan_service import run_and_store_scan, record_to_dict

router = APIRouter(prefix="/api/scan", tags=["patches"])


@router.get("/{scan_id}/patches")
def get_patches(scan_id: str, db: Session = Depends(get_db)):
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")
    return auto_patch.generate_patches(record.code)


@router.post("/{scan_id}/apply-patch")
def apply_patch(scan_id: str, payload: ApplyPatchRequest, db: Session = Depends(get_db)):
    """
    Apply = create a new, derived ScanRecord from the rewritten code and
    re-run real inference on it (docs/APPLY_PATCH_LOOP_DESIGN.md §1) -- the
    original record is never mutated, so "revert" is free (just navigate
    back to it). Never writes to disk (no scan source in this app has a
    real file to write to except Watch Mode, explicitly out of scope here
    per the design's §1).

    The rewrite is always recomputed here from the scan's own stored code
    (recommendations.suggest_secure_rewrite), NOT taken from the request
    body -- `payload.patch_id` is informational only. This guarantees the
    code that gets safety-checked and the code that gets applied are
    exactly the same string; trusting a client-supplied "already fixed"
    snippet for a safety-critical decision would let a tampered request
    bypass the block below entirely.
    """
    record = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")

    rewrite = recommendations.suggest_secure_rewrite(record.code)

    if not rewrite["changed"]:
        raise HTTPException(status_code=400, detail="No auto-fixable pattern found in this scan -- nothing to apply.")

    # CRITICAL SAFETY CHECK -- extends, does not bypass, the same honesty
    # rule patch_safety.py already enforces on AutoPatch.tsx's own cards
    # (size_known) and in suggest_secure_rewrite's own change-log labeling.
    # If ANY occurrence in the rewrite used an unknown/placeholder
    # destination size, the rewritten text contains literal template/
    # comment text (e.g. "dest_size PLACEHOLDER"), not valid, compilable C
    # -- applying and re-scanning it would feed the model a fabricated
    # snippet and produce a misleading comparison. Block the WHOLE apply
    # rather than partially applying only the safe occurrences, so the
    # derived scan's code is never a mix of real fixes and unresolved
    # templates.
    if rewrite["requires_manual_sizing"]:
        raise HTTPException(status_code=422, detail={
            "blocked": True,
            "reason": (
                "One or more of the generated fixes use a dest_size PLACEHOLDER, not a real, "
                "statically-known buffer capacity -- the destination is a pointer parameter, not a "
                "stack array with a visible declaration, so its real size cannot be determined from "
                "this code alone."
            ),
            "note": patch_safety.UNKNOWN_CAPACITY_NOTE,
            "changes": rewrite["changes"],
        })

    derived = run_and_store_scan(
        db,
        code=rewrite["rewritten_code"],
        project_name=record.project_name,
        filename=record.filename,
        model_choice=record.model_used or "XGBoost",
        source="apply-patch",
        batch_id=None,  # a derived scan is its own standalone record, not part of the original's batch
    )
    derived.derived_from_scan_id = record.id
    db.commit()
    db.refresh(derived)

    return {
        "applied": True,
        "patch_id": payload.patch_id,
        "original_scan_id": record.id,
        "derived_scan_id": derived.id,
        "changes": rewrite["changes"],
        # include_code=True on both -- the before/after comparison (diff +
        # risk score, docs/APPLY_PATCH_LOOP_DESIGN.md §3) needs both code
        # strings, and this keeps the response fully self-contained rather
        # than requiring the frontend to separately trust whatever's
        # currently loaded in page state to still be the right "original".
        "original": record_to_dict(record, include_code=True),
        "derived": record_to_dict(derived, include_code=True),
    }
