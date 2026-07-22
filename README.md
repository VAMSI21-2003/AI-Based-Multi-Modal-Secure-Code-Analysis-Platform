# SecureCode AI — Multi-Modal Code Vulnerability Detection

AI-powered secure code analysis platform combining **AST structural features**,
**software quality metrics**, and **CodeBERT semantic embeddings**, fused into
a single feature vector and classified by trained **XGBoost** / **Random
Forest** models. FastAPI backend, React + Vite frontend. See
`paper/research_paper.md` for the full methodology and evaluation.

- **Run it:** see `DOCKER.md` for the one-command Docker setup, or run
  `backend/` (`uvicorn main:app --reload`) and `frontend/` (`npm run dev`)
  directly against a Python 3.11 venv + Node 20.
- **Architecture:** `app/` holds the original trained ML pipeline
  (AST/metrics/CodeBERT extraction, XGBoost/Random Forest); `backend/` is the
  FastAPI API layer that reuses it (via `ml_bridge.py`) for the live
  platform; `frontend/` is the React dashboard.

---

## Configuration

- **`frontend/.env.example`** — `VITE_SCAN_TIMEOUT_MS` (default 1200000 / 20
  min): timeout for scan-triggering requests (single-file, batch/ZIP/folder,
  GitHub repo, live editor). A large real-world repo can legitimately take
  minutes to scan — bumped from 10 to 20 min after per-function inference
  (`docs/PER_FUNCTION_INFERENCE_DESIGN.md`) measured a real 200-file GitHub
  scan (curl) at 797.5s server-side, already past the old default — this is
  a **stopgap**, not the real fix. The proper fix for very large repos is an
  async job (submit → poll status/progress → fetch result) instead of one
  long blocking HTTP request; out of scope for now.
- **`backend/.env.example`** — `CORS_ALLOWED_ORIGINS` (comma-separated,
  defaults to the Vite dev server / docker-compose ports if unset),
  `SECURECODE_DB_PATH` (override the SQLite data file location),
  `SCAN_BLOCKING` (CI-only, see `docs/CI_CD.md`), `HF_TOKEN` (optional,
  raises HuggingFace's download rate limit for the CodeBERT weights),
  `LOG_LEVEL` (default `INFO`; see `backend/logging_config.py`).

---

## Scope: no authentication

This platform has no authentication or user accounts anywhere in the
FastAPI app — every endpoint is open to anyone who can reach the process.
This is a **deliberate scope decision**, not an oversight: it's built and
evaluated as a single-operator academic/research tool (run locally or in
one Docker Compose stack for one person's own repos), not a multi-tenant
service, so there is no second user's data to protect it from and no
session/identity concept the rest of the design assumes exists.

**What a real production deployment would need instead**: authenticated
sessions (or an API key) in front of every route, per-user scan history
instead of one shared SQLite database, and the CORS/network-exposure
posture revisited accordingly (`CORS_ALLOWED_ORIGINS`, see
[Configuration](#configuration), currently assumes a trusted single-user
frontend, not arbitrary third-party origins). None of that is implemented
here, and bolting it on is a real project on its own, not a quick addition
to this one.

---

## CI/CD

Every push, pull request, and manual trigger runs the pipeline defined in
[`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml): **backend-validation**
and **frontend-validation** run in parallel; on a pull request or manual run,
both gate a **security-scan** job that runs this project's real
CodeBERT/AST/Metrics/XGBoost pipeline — against just the files changed in the
PR (`git diff`) on a pull request, or the whole repository on a manual
`workflow_dispatch` run — and uploads findings as SARIF (GitHub's Security
tab) plus a PR summary comment; a **final-status** job reports one
unambiguous pass/fail result. The security-scan job is **non-blocking by
default** (`SCAN_BLOCKING`, see `docs/CI_CD.md` §5) and does **not** run on
every plain push to `main`.

Full explanation — job-by-job breakdown, exactly what is and isn't scanned,
the security fail policy and why it's CRITICAL-only, how the scanner
integrates without faking results, how to run every check locally, and this
pipeline's honest limitations — is in **[`docs/CI_CD.md`](docs/CI_CD.md)**.
