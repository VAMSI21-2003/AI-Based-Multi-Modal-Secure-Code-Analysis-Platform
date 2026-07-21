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

## CI/CD

Every push, pull request, and manual trigger runs the pipeline defined in
[`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml): **backend-validation**
and **frontend-validation** run in parallel, both gate a **security-scan** job
that runs this project's real CodeBERT/AST/Metrics/XGBoost pipeline against a
small demo fixture, and a **final-status** job reports one unambiguous
pass/fail result.

Full explanation — job-by-job breakdown, the security fail policy and why
it's CRITICAL-only, how the scanner integrates without faking results, how to
run every check locally, and this pipeline's honest limitations — is in
**[`docs/CI_CD.md`](docs/CI_CD.md)**.
