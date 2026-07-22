# =============================================================================
# test_derived_scan_schema.py -- real test for the derived_from_scan_id
# column (docs/APPLY_PATCH_LOOP_DESIGN.md, Phase 1: schema). Confirms the
# link from a patched/derived scan back to its original round-trips through
# an actual commit + a fresh SessionLocal() (simulating a backend restart --
# same rigor as test_github_batch_meta.py's equivalent test), and that
# ordinary scans keep the column NULL.
# =============================================================================

import pytest

from database import SessionLocal, ScanRecord, new_id

ORIGINAL_ID = "derivtest_orig1"
DERIVED_ID = "derivtest_der1"


@pytest.fixture
def original_and_derived_rows():
    db = SessionLocal()
    db.query(ScanRecord).filter(ScanRecord.id.in_([ORIGINAL_ID, DERIVED_ID])).delete(synchronize_session=False)
    db.add(ScanRecord(id=ORIGINAL_ID, code="void f(void) { strcpy(a, b); }", verdict="VULNERABLE"))
    db.add(ScanRecord(id=DERIVED_ID, code="void f(void) { strncpy(a, b, sizeof(a) - 1); }",
                       verdict="NOT VULNERABLE", derived_from_scan_id=ORIGINAL_ID))
    db.commit()
    db.close()
    yield ORIGINAL_ID, DERIVED_ID
    db = SessionLocal()
    db.query(ScanRecord).filter(ScanRecord.id.in_([ORIGINAL_ID, DERIVED_ID])).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_derived_scan_link_survives_a_fresh_session(original_and_derived_rows):
    original_id, derived_id = original_and_derived_rows
    # A brand-new SessionLocal() against the same on-disk file is what
    # happens after a backend restart -- no process memory is reused, only
    # what was actually committed (same pattern test_github_batch_meta.py
    # uses to prove commit_sha isn't just an in-memory artifact).
    fresh_session = SessionLocal()
    try:
        derived = fresh_session.get(ScanRecord, derived_id)
        assert derived is not None
        assert derived.derived_from_scan_id == original_id

        original = fresh_session.get(ScanRecord, original_id)
        assert original is not None
        assert original.derived_from_scan_id is None
    finally:
        fresh_session.close()


def test_ordinary_scan_created_via_new_id_has_no_derived_link():
    # A regular scan (no apply-patch involved) must default the column to
    # NULL, not an empty string or 0 -- this is how callers distinguish "an
    # ordinary scan" from "a derived one" throughout the API/UI.
    record = ScanRecord(id=new_id(), code="void f(void) {}")
    assert record.derived_from_scan_id is None
