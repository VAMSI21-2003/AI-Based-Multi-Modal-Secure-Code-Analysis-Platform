# CI Demo Scan Samples

These two files exist for **one reason only**: to give the `security-scan` CI
job something real to scan and demonstrate.

This project's own source is Python + TypeScript/React — it has no `.c`/`.cpp`/`.h`
files of its own, so scanning the repository root finds nothing (an honest but
unimpressive demo). These fixtures are small, clearly-labeled, non-production
C snippets that let the pipeline show both the pass path (a safe file) and the
fail path (a deliberately vulnerable file) without touching any real source
file anywhere else in this repository.

Nothing here is imported, compiled, or executed by the platform. They exist
purely as scan input for `backend/ci_scan.py` in CI.

- `vulnerable_example.c` — an unbounded `strcpy()`, the same CWE-120 pattern
  used throughout this project's own demo/test scans elsewhere in the app.
- `safe_example.c` — the bounds-checked `strncpy()` fix for the same function.
