# =============================================================================
# github_service.py -- Phase 6: GitHub Mode.
#
# Clones a public GitHub (or any plain git) repository to a temporary local
# directory, scans every matching source file through the EXISTING pipeline
# (scan_service.run_and_store_scan, unchanged), records the commit history
# via `git log`, then deletes the temporary clone -- only the resulting
# ScanRecord rows (tagged with a batch_id) persist, exactly like any other
# batch scan. This means Project Scanner, Dependency Graph, and the Batch
# PDF export all work on a GitHub-cloned repo for free, with zero new code
# in any of those pages.
#
# Security note: the repo URL is validated to be a plain http(s) URL (no
# `-`-prefixed strings, no ssh/local paths) and passed to `git` as a real
# argv list (never through a shell), so there is no command-injection
# surface. Nothing in the cloned repo is ever executed -- it is only parsed
# (tree-sitter) and read as text (CodeBERT tokenizer), the same as any
# uploaded file.
# =============================================================================

import os
import re
import shutil
import subprocess
import tempfile
import uuid

from database import SessionLocal
from scan_service import run_and_store_scan
from routers.scan import CODE_EXTENSIONS, EXCLUDED_DIR_NAMES

MAX_REPO_FILES = 200
MAX_FILE_SIZE = 512_000
CLONE_TIMEOUT_SEC = 90
CLONE_DEPTH = 50

_URL_RE = re.compile(r"^https?://[A-Za-z0-9._~%\-]+(/[A-Za-z0-9._~%\-./]*)?$")

_COMMIT_HISTORY = {}  # batch_id -> list of commit dicts (in-memory, mirrors watch_service's session store)


def _validate_url(url: str) -> str:
    url = (url or "").strip()
    if not _URL_RE.match(url):
        raise ValueError("Only plain http(s) git URLs are supported (e.g. https://github.com/owner/repo.git)")
    return url


def _run_git(args, cwd=None, timeout=CLONE_TIMEOUT_SEC):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False,
    )


def _get_commit_history(repo_dir: str, limit: int = 20) -> list:
    sep = "\x1f"
    fmt = sep.join(["%H", "%an", "%ad", "%s"])
    result = _run_git(["log", f"-{limit}", f"--pretty=format:{fmt}", "--date=iso-strict"], cwd=repo_dir, timeout=20)
    if result.returncode != 0:
        return []
    commits = []
    for line in result.stdout.splitlines():
        parts = line.split(sep)
        if len(parts) != 4:
            continue
        commits.append({"hash": parts[0][:10], "author": parts[1], "date": parts[2], "message": parts[3]})
    return commits


def scan_repo(repo_url: str, project_name: str = None) -> dict:
    url = _validate_url(repo_url)
    repo_name = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    project_name = project_name or repo_name

    tmp_dir = tempfile.mkdtemp(prefix="secure_code_ai_ghmode_")
    try:
        clone_result = _run_git(
            ["clone", "--depth", str(CLONE_DEPTH), "--single-branch", url, tmp_dir],
            timeout=CLONE_TIMEOUT_SEC,
        )
        if clone_result.returncode != 0:
            raise RuntimeError(f"git clone failed: {clone_result.stderr.strip()[:400]}")

        commits = _get_commit_history(tmp_dir, limit=20)

        matched_files = []
        for root, dirs, files in os.walk(tmp_dir):
            dirs[:] = [d for d in dirs if d != ".git" and d.lower() not in EXCLUDED_DIR_NAMES]
            for name in files:
                if os.path.splitext(name)[1].lower() not in CODE_EXTENSIONS:
                    continue
                full = os.path.join(root, name)
                try:
                    if os.path.getsize(full) > MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue
                matched_files.append(full)
        matched_files = matched_files[:MAX_REPO_FILES]

        if not matched_files:
            raise RuntimeError("No scannable .c/.cpp/.h files found in this repository.")

        batch_id = "gh_" + uuid.uuid4().hex[:10]
        db = SessionLocal()
        scanned = 0
        try:
            for full in matched_files:
                try:
                    with open(full, "r", encoding="utf-8", errors="replace") as fh:
                        code = fh.read()
                except OSError:
                    continue
                if not code.strip():
                    continue
                rel_path = os.path.relpath(full, tmp_dir).replace("\\", "/")
                run_and_store_scan(db, code, project_name, rel_path, "XGBoost", "github", batch_id=batch_id)
                scanned += 1
        finally:
            db.close()

        _COMMIT_HISTORY[batch_id] = commits

        return {
            "batch_id": batch_id, "repo_url": url, "project_name": project_name,
            "files_scanned": scanned, "files_found": len(matched_files), "commits_recorded": len(commits),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def get_commit_history(batch_id: str) -> list:
    return _COMMIT_HISTORY.get(batch_id, [])
