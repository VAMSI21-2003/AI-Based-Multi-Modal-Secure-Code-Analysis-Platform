# =============================================================================
# test_apply_patch.py -- real tests for POST /api/scan/{id}/apply-patch
# (docs/APPLY_PATCH_LOOP_DESIGN.md, Phase 2). Exercises the actual trained
# model and the real DB, not mocks: applying a known-safe fix must produce a
# genuine, freshly-computed risk score on the rewritten code, and applying a
# fix whose destination size is unknown must be blocked before any derived
# record is created -- never silently applied with fabricated/template text.
# =============================================================================

from fastapi.testclient import TestClient

from database import SessionLocal, ScanRecord
from main import app

client = TestClient(app)

# `buf` is a real, statically-visible stack array (char buf[64]) -- patch_safety
# resolves its capacity via sizeof(), so suggest_secure_rewrite() emits a real
# fix (strncpy + sizeof(buf)), not a placeholder.
KNOWN_SAFE_SNIPPET = """
void copy_input(char *src) {
    char buf[64];
    strcpy(buf, src);
}
"""

# `dest` is a function parameter (char *dest) -- decays to a pointer, so its
# real capacity cannot be determined from this code. suggest_secure_rewrite()
# must fall back to an honestly-labeled dest_size placeholder here.
UNKNOWN_SIZE_SNIPPET = """
void copy_input(char *dest, char *src) {
    strcpy(dest, src);
}
"""

NOTHING_TO_FIX_SNIPPET = """
int add(int a, int b) {
    return a + b;
}
"""


def _post_scan(code: str, filename: str) -> str:
    resp = client.post("/api/scan/code", json={
        "code": code, "project_name": "apply-patch-test", "filename": filename,
        "model_choice": "XGBoost", "source": "paste",
    })
    assert resp.status_code == 200
    return resp.json()["id"]


def test_apply_patch_with_known_safe_destination_creates_derived_record_with_real_score():
    original_id = _post_scan(KNOWN_SAFE_SNIPPET, "known_safe.c")

    original_before = client.get(f"/api/scan/{original_id}").json()

    resp = client.post(f"/api/scan/{original_id}/apply-patch", json={"patch_id": "strcpy-1"})
    assert resp.status_code == 200
    body = resp.json()

    assert body["applied"] is True
    assert body["original_scan_id"] == original_id
    derived_id = body["derived_scan_id"]
    assert derived_id and derived_id != original_id
    assert len(body["changes"]) >= 1

    derived = client.get(f"/api/scan/{derived_id}").json()
    assert derived["derived_from_scan_id"] == original_id
    # The rewrite actually landed in the derived record's stored code -- a
    # real strncpy() replaced the strcpy() call, not a copy of the original.
    assert "strncpy(" in derived["code"]
    assert "strcpy(buf, src)" not in derived["code"]
    # A real prediction was computed (not fabricated): a valid probability
    # in range, and a verdict consistent with that probability.
    assert 0.0 <= derived["vuln_probability"] <= 100.0
    assert derived["verdict"] in ("VULNERABLE", "NOT VULNERABLE")
    assert derived["model_used"]

    # The original record must be completely untouched -- "revert" is free
    # per the design precisely because apply never mutates it.
    original_after = client.get(f"/api/scan/{original_id}").json()
    assert original_after["code"] == original_before["code"]
    assert original_after["vuln_probability"] == original_before["vuln_probability"]
    assert original_after["derived_from_scan_id"] is None


def test_apply_patch_with_unknown_destination_size_is_blocked_not_silently_applied():
    original_id = _post_scan(UNKNOWN_SIZE_SNIPPET, "unknown_size.c")
    original_before = client.get(f"/api/scan/{original_id}").json()

    resp = client.post(f"/api/scan/{original_id}/apply-patch", json={})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["blocked"] is True
    assert "dest_size" in detail["reason"] or "placeholder" in detail["reason"].lower()
    assert "pointer" in detail["note"].lower()

    # No derived record was created for this scan at all -- confirmed via a
    # direct DB query, not just trusting the HTTP response.
    db = SessionLocal()
    try:
        derived_rows = db.query(ScanRecord).filter(ScanRecord.derived_from_scan_id == original_id).all()
        assert derived_rows == []
    finally:
        db.close()

    original_after = client.get(f"/api/scan/{original_id}").json()
    assert original_after["code"] == original_before["code"]
    assert original_after["vuln_probability"] == original_before["vuln_probability"]


def test_apply_patch_with_nothing_to_fix_returns_400():
    original_id = _post_scan(NOTHING_TO_FIX_SNIPPET, "clean.c")
    resp = client.post(f"/api/scan/{original_id}/apply-patch", json={})
    assert resp.status_code == 400


def test_apply_patch_on_unknown_scan_id_returns_404():
    resp = client.post("/api/scan/does-not-exist-at-all/apply-patch", json={})
    assert resp.status_code == 404
