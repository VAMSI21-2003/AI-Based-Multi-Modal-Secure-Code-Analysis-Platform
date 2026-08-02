# =============================================================================
# test_batch_upload_security.py -- Zip Slip / path-traversal guard tests, and
# scan-completeness (skip-reason) reporting tests for POST /api/scan/batch.
#
# The batch endpoint never extracts ZIP entries to disk (everything is read
# into memory and stored as a DB column), so a traversal member name cannot
# actually escape a directory today -- but is_safe_archive_member_path() is
# tested here as defense-in-depth, and because the batch response now reports
# WHY files were skipped (a real product-honesty requirement), that reporting
# itself needs a regression test.
#
# POST /api/scan/batch is now async (docs/ASYNC_SCAN_DESIGN.md): it returns
# {batch_id, status: "queued", files_total} immediately instead of the full
# result. TestClient runs the whole ASGI cycle -- including BackgroundTasks --
# to completion before .post() returns control, so by the time these tests
# poll GET /api/scan/jobs/{batch_id} once, the job is already "succeeded" in
# practice; _poll_until_done below still loops properly rather than assuming
# that, so these tests would keep working even if that timing changed.
# =============================================================================

import io
import time
import zipfile

from fastapi.testclient import TestClient

from main import app
from routers.scan import is_safe_archive_member_path

client = TestClient(app)


def _poll_until_done(batch_id: str, timeout_sec: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        job = client.get(f"/api/scan/jobs/{batch_id}").json()
        if job["status"] in ("succeeded", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {batch_id} did not finish within {timeout_sec}s")

VULNERABLE_SNIPPET = """
void copy_input(char *dest, const char *src) {
    strcpy(dest, src);
}
"""


# ── Unit tests: is_safe_archive_member_path ─────────────────────────────────

def test_valid_nested_path_is_safe():
    assert is_safe_archive_member_path("src/util/parse.c") is True


def test_parent_traversal_is_rejected():
    assert is_safe_archive_member_path("../evil.c") is False


def test_deep_parent_traversal_is_rejected():
    assert is_safe_archive_member_path("../../etc/passwd") is False


def test_traversal_inside_a_nested_path_is_rejected():
    assert is_safe_archive_member_path("src/../../evil.c") is False


def test_absolute_posix_path_is_rejected():
    assert is_safe_archive_member_path("/etc/passwd") is False


def test_absolute_windows_path_is_rejected():
    assert is_safe_archive_member_path(r"C:\Windows\System32\evil.c") is False


def test_backslash_traversal_is_rejected():
    assert is_safe_archive_member_path(r"..\..\evil.c") is False


# ── Integration test: malicious ZIP member is skipped, valid one is scanned ─

def _zip_bytes(entries: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_batch_upload_rejects_traversal_member_but_scans_the_safe_one():
    zip_bytes = _zip_bytes({
        "src/vuln.c": VULNERABLE_SNIPPET,
        "../evil.c": VULNERABLE_SNIPPET,
    })
    response = client.post(
        "/api/scan/batch",
        data={"project_name": "zip-slip-test", "model_choice": "XGBoost"},
        files={"files": ("repo.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 200
    submitted = response.json()
    assert submitted["status"] == "queued"
    assert submitted["files_total"] == 1

    job = _poll_until_done(submitted["batch_id"])
    assert job["status"] == "succeeded"
    result = job["result"]
    assert result["total_files_scanned"] == 1
    assert any("unsafe path" in reason for reason in result["skip_reasons"])
    assert result["results"][0]["filename"] == "src/vuln.c"


def test_batch_upload_reports_skip_reasons_for_unsupported_files():
    zip_bytes = _zip_bytes({
        "src/vuln.c": VULNERABLE_SNIPPET,
        "README.md": "not source code",
    })
    response = client.post(
        "/api/scan/batch",
        data={"project_name": "skip-reason-test", "model_choice": "XGBoost"},
        files={"files": ("repo.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 200
    submitted = response.json()

    job = _poll_until_done(submitted["batch_id"])
    assert job["status"] == "succeeded"
    result = job["result"]
    assert result["files_detected"] == 1
    assert result["total_files_scanned"] == 1
    assert any("unsupported extension" in reason for reason in result["skip_reasons"])


def test_batch_upload_rejects_zip_with_too_many_members():
    from routers.scan import MAX_ZIP_MEMBERS
    entries = {f"src/f{i}.c": "void f(void) {}" for i in range(MAX_ZIP_MEMBERS + 1)}
    zip_bytes = _zip_bytes(entries)
    response = client.post(
        "/api/scan/batch",
        data={"project_name": "zip-bomb-count-test", "model_choice": "XGBoost"},
        files={"files": ("bomb.zip", zip_bytes, "application/zip")},
    )
    # Entire archive is rejected as a suspected zip bomb -> no scannable files survive.
    assert response.status_code == 400


def test_batch_upload_handles_corrupt_zip_without_crashing():
    response = client.post(
        "/api/scan/batch",
        data={"project_name": "corrupt-zip-test", "model_choice": "XGBoost"},
        files={"files": ("broken.zip", b"not actually a zip file", "application/zip")},
    )
    # No scannable files survive a corrupt archive -> the existing 400 path,
    # not a 500 -- confirms BadZipFile is caught, not propagated as a crash.
    assert response.status_code == 400
