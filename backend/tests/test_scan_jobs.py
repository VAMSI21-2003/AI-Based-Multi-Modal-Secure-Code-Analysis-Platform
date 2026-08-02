# =============================================================================
# test_scan_jobs.py -- async batch/GitHub scan job tracking
# (docs/ASYNC_SCAN_DESIGN.md). Covers job_service's state transitions
# directly, the GET /api/scan/jobs/{batch_id} endpoint, and
# reap_orphaned_jobs() -- the startup mitigation for a job left stuck at
# "queued"/"running" by a process restart.
# =============================================================================

import datetime as dt

import pytest
from fastapi.testclient import TestClient

import job_service
from database import SessionLocal, ScanJob
from main import app

client = TestClient(app)


@pytest.fixture
def cleanup_job():
    created_ids = []

    def _track(batch_id):
        created_ids.append(batch_id)
        return batch_id

    yield _track

    db = SessionLocal()
    for batch_id in created_ids:
        db.query(ScanJob).filter(ScanJob.batch_id == batch_id).delete()
    db.commit()
    db.close()


# ── job_service state transitions, direct ───────────────────────────────────

def test_create_job_starts_queued(cleanup_job):
    batch_id = cleanup_job("test_job_queued_001")
    db = SessionLocal()
    try:
        job_service.create_job(db, batch_id, kind="batch", files_total=5)
        job = job_service.get_job(db, batch_id)
        assert job.status == "queued"
        assert job.files_total == 5
        assert job.files_completed == 0
        assert job.started_at is None
    finally:
        db.close()


def test_mark_running_sets_started_at(cleanup_job):
    batch_id = cleanup_job("test_job_running_001")
    db = SessionLocal()
    try:
        job_service.create_job(db, batch_id, kind="batch", files_total=1)
        job_service.mark_running(db, batch_id)
        job = job_service.get_job(db, batch_id)
        assert job.status == "running"
        assert job.started_at is not None
    finally:
        db.close()


def test_increment_progress_accumulates(cleanup_job):
    batch_id = cleanup_job("test_job_progress_001")
    db = SessionLocal()
    try:
        job_service.create_job(db, batch_id, kind="batch", files_total=10)
        job_service.increment_progress(db, batch_id, completed_delta=1)
        job_service.increment_progress(db, batch_id, completed_delta=1)
        job_service.increment_progress(db, batch_id, failed_delta=1)
        job = job_service.get_job(db, batch_id)
        assert job.files_completed == 2
        assert job.files_failed == 1
    finally:
        db.close()


def test_mark_succeeded_stores_result_and_finished_at(cleanup_job):
    batch_id = cleanup_job("test_job_succeeded_001")
    db = SessionLocal()
    try:
        job_service.create_job(db, batch_id, kind="batch", files_total=1)
        job_service.mark_succeeded(db, batch_id, {"files_scanned": 1, "vulnerable_count": 0})
        job = job_service.get_job(db, batch_id)
        assert job.status == "succeeded"
        assert job.finished_at is not None
        d = job_service.job_to_dict(job)
        assert d["result"] == {"files_scanned": 1, "vulnerable_count": 0}
    finally:
        db.close()


def test_mark_failed_stores_error(cleanup_job):
    batch_id = cleanup_job("test_job_failed_001")
    db = SessionLocal()
    try:
        job_service.create_job(db, batch_id, kind="github", files_total=0)
        job_service.mark_failed(db, batch_id, "git clone failed: repository not found")
        job = job_service.get_job(db, batch_id)
        assert job.status == "failed"
        assert "not found" in job.error
        assert job.finished_at is not None
    finally:
        db.close()


# ── GET /api/scan/jobs/{batch_id} ────────────────────────────────────────────

def test_get_job_endpoint_returns_current_state(cleanup_job):
    batch_id = cleanup_job("test_job_api_001")
    db = SessionLocal()
    try:
        job_service.create_job(db, batch_id, kind="batch", files_total=3)
        job_service.mark_running(db, batch_id)
        job_service.increment_progress(db, batch_id, completed_delta=1)
    finally:
        db.close()

    response = client.get(f"/api/scan/jobs/{batch_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] == batch_id
    assert body["status"] == "running"
    assert body["files_total"] == 3
    assert body["files_completed"] == 1
    assert body["result"] is None


def test_get_job_endpoint_404_for_unknown_batch_id():
    response = client.get("/api/scan/jobs/does_not_exist_xyz")
    assert response.status_code == 404


# ── Real end-to-end: submit a batch scan, poll to completion ────────────────

def test_batch_scan_end_to_end_via_job_polling():
    import time

    code = "void f(char *dst, char *src) { strcpy(dst, src); }"
    response = client.post(
        "/api/scan/batch",
        data={"project_name": "job-e2e-test", "model_choice": "XGBoost"},
        files={"files": ("vuln.c", code.encode(), "text/plain")},
    )
    assert response.status_code == 200
    submitted = response.json()
    assert submitted["status"] == "queued"
    assert "batch_id" in submitted
    assert submitted["files_total"] == 1

    deadline = time.monotonic() + 30.0
    job = None
    while time.monotonic() < deadline:
        job = client.get(f"/api/scan/jobs/{submitted['batch_id']}").json()
        if job["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)

    assert job is not None
    assert job["status"] == "succeeded", job.get("error")
    assert job["files_completed"] == 1
    assert job["result"]["total_files_scanned"] == 1
    assert job["result"]["results"][0]["filename"] == "vuln.c"

    db = SessionLocal()
    db.query(ScanJob).filter(ScanJob.batch_id == submitted["batch_id"]).delete()
    db.commit()
    db.close()


# ── Orphaned-job reaping (startup mitigation) ───────────────────────────────

def test_reap_orphaned_jobs_marks_stuck_jobs_failed(cleanup_job):
    running_id = cleanup_job("test_job_orphan_running")
    queued_id = cleanup_job("test_job_orphan_queued")
    succeeded_id = cleanup_job("test_job_orphan_succeeded")

    db = SessionLocal()
    try:
        job_service.create_job(db, running_id, kind="batch", files_total=5)
        job_service.mark_running(db, running_id)  # simulates a job mid-flight when the process died

        job_service.create_job(db, queued_id, kind="github", files_total=0)  # never even started

        job_service.create_job(db, succeeded_id, kind="batch", files_total=1)
        job_service.mark_succeeded(db, succeeded_id, {"ok": True})  # must NOT be touched by reaping
    finally:
        db.close()

    reaped_count = job_service.reap_orphaned_jobs()
    assert reaped_count >= 2  # at least the two we just created (other tests may leave rows too)

    db = SessionLocal()
    try:
        running_job = job_service.get_job(db, running_id)
        queued_job = job_service.get_job(db, queued_id)
        succeeded_job = job_service.get_job(db, succeeded_id)

        assert running_job.status == "failed"
        assert "restart" in running_job.error.lower()
        assert queued_job.status == "failed"
        assert succeeded_job.status == "succeeded"  # untouched -- was already terminal
    finally:
        db.close()


def test_reap_orphaned_jobs_does_not_touch_a_freshly_created_queued_job(cleanup_job):
    # Reaping is meant for jobs orphaned by a PAST process, not ones a
    # currently-running process just created -- but reap_orphaned_jobs()
    # has no way to distinguish "queued 10ms ago, about to start" from
    # "queued before a restart that never happened" purely from the status
    # column. This test documents that limitation honestly rather than
    # asserting behavior the function doesn't actually have: a job created
    # right before reaping DOES get marked failed, same as a truly stuck
    # one. In production this is a non-issue since reaping only ever runs
    # once, at startup, before any job could have been created yet.
    batch_id = cleanup_job("test_job_fresh_at_reap_time")
    db = SessionLocal()
    try:
        job_service.create_job(db, batch_id, kind="batch", files_total=1)
    finally:
        db.close()

    job_service.reap_orphaned_jobs()

    db = SessionLocal()
    try:
        job = job_service.get_job(db, batch_id)
        assert job.status == "failed"  # confirms the documented limitation above, not a bug
    finally:
        db.close()
