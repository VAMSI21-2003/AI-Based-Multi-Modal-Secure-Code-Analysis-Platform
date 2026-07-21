# =============================================================================
# test_github_batch_meta.py -- real tests for GitHub-scan repository
# provenance persistence (github_batch_meta, a table additive alongside the
# existing `scans` table): commit SHA, branch, and detected/analyzed/skipped
# file counts for a GitHub Mode scan. This is general GitHub-scanner
# functionality, independent of any external tool -- SonarQube-specific
# comparison functionality (the former Live Repository Comparison feature)
# has been removed from the product; see docs/BASELINE_BEFORE_HARDENING.md.
#
# Exercises the real SQLite database (backend/data/platform.db) the running
# app uses -- there is no separate test-database config in this project (see
# conftest.py) -- but every row this file creates is deleted in teardown, so
# running the suite never leaves demo/scan-history data behind.
# =============================================================================

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal, GitHubBatchMeta
import github_service
from main import app

client = TestClient(app)

TEST_BATCH_ID = "gh_test0000ab"


@pytest.fixture
def batch_meta_row():
    db = SessionLocal()
    db.query(GitHubBatchMeta).filter(GitHubBatchMeta.batch_id == TEST_BATCH_ID).delete()
    db.add(GitHubBatchMeta(
        batch_id=TEST_BATCH_ID,
        repo_url="https://github.com/madler/zlib",
        repo_name="zlib",
        branch="develop",
        commit_sha="a" * 40,
        files_detected=100,
        files_analyzed=100,
        files_skipped=0,
        skip_reasons="",
        scanned_at=dt.datetime.utcnow(),
    ))
    db.commit()
    db.close()
    yield TEST_BATCH_ID
    db = SessionLocal()
    db.query(GitHubBatchMeta).filter(GitHubBatchMeta.batch_id == TEST_BATCH_ID).delete()
    db.commit()
    db.close()


def test_new_scan_batch_meta_stores_commit_sha(batch_meta_row):
    result = github_service.get_batch_meta(batch_meta_row)
    assert result is not None
    assert result["commit_sha"] == "a" * 40
    assert result["branch"] == "develop"
    assert result["repo_name"] == "zlib"


def test_batch_without_meta_row_does_not_crash():
    # Simulates a scan record from before this feature existed -- no row in
    # github_batch_meta at all. Must return None cleanly, never raise.
    result = github_service.get_batch_meta("gh_never_existed_00")
    assert result is None


def test_api_returns_commit_sha_for_known_batch(batch_meta_row):
    response = client.get(f"/api/github/{batch_meta_row}/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["commit_sha"] == "a" * 40
    assert body["repo_url"] == "https://github.com/madler/zlib"


def test_api_returns_404_for_unknown_batch():
    response = client.get("/api/github/gh_never_existed_00/meta")
    assert response.status_code == 404


def test_commit_sha_survives_a_fresh_session(batch_meta_row):
    # A brand-new SessionLocal() against the same on-disk SQLite file is
    # exactly what happens after a backend restart: no process memory is
    # reused, only what was actually committed to disk. This is why the
    # commit SHA lives in `github_batch_meta` (a real table) rather than the
    # in-memory `_COMMIT_HISTORY` dict, which is documented to NOT survive
    # a restart.
    fresh_session = SessionLocal()
    try:
        row = fresh_session.get(GitHubBatchMeta, batch_meta_row)
        assert row is not None
        assert row.commit_sha == "a" * 40
    finally:
        fresh_session.close()
