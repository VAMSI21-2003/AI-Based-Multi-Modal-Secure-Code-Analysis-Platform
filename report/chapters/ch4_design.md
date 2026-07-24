# CHAPTER 4: SYSTEM DESIGN AND DEVELOPMENT

## 4.1 System Architecture (High-Level Design)

### 4.1.1 Conceptual Design

The system separates cleanly into three layers that are developed, versioned, and can be reasoned
about independently:

1. **`app/` — the core ML library.** Contains the original feature-extraction and prediction logic
   (`predictor.py`, `utils.py`): AST/metrics extraction, CodeBERT embedding, and model loading/
   inference. This layer has no knowledge of HTTP, FastAPI, or the database — it is a plain Python
   library.
2. **`backend/` — the FastAPI service layer.** Wraps `app/` via `backend/ml_bridge.py`, which imports
   the extraction and prediction functions directly rather than reimplementing them, and adds
   everything a web application needs that a bare ML library does not provide: request/response
   schemas, SQLite-backed persistence (`database.py`), scan history, remediation logic
   (`recommendations.py`), automated patching (`auto_patch.py`, `patch_safety.py`, `rewrite_rules.py`),
   whole-project analysis (`repo_analysis.py`, `code_intelligence.py`), GitHub integration
   (`github_service.py`), CI scanning (`ci_scan.py`), and 17 FastAPI routers exposing this
   functionality as a REST API.
3. **`frontend/` — the React/TypeScript presentation layer.** Consumes the backend's REST API and
   presents it across purpose-built pages, described in Section 4.4.

Figure 4.1 (Section 4.1.2) shows this layering; the key design principle is that the trained model and
its feature-extraction code are never duplicated between the offline training pipeline and the online
serving path — both call the same `app/` functions, so a prediction made through the web application
uses exactly the same feature computation as the model's own training and evaluation.

### 4.1.2 Component Diagram

**Figure 4.1: High-level system architecture — three-layer separation between the ML core, FastAPI, and React**
(`report/figures/fig_architecture.png`). The frontend talks to the backend only through the REST API;
`ml_bridge.py` is the only path from the API layer into the shared ML core (`app/predictor.py`,
`app/utils.py`); and the backend loads the trained model artifacts once at startup rather than per
request. See Figure 3.1 (Chapter 3.2.1) for how those artifacts are produced.

## 4.2 Detailed Design (Low-Level Design)

### 4.2.1 Data Flow

For a single scanned function: source code → `ml_bridge` calls `app.utils.extract_ast_features` and
`extract_metric_features` (structural/metric branches) and `app.predictor`'s CodeBERT loader (semantic
branch) → the three vectors are fused into the same 792-dimensional layout the offline pipeline used →
`predict_with_model` runs the loaded XGBoost or Random Forest model → the verdict, probability,
confidence, and auxiliary artifacts (AST tree for the UI viewer, deterministic line-risk scan,
approximate feature-contribution scores, PCA-projected embedding coordinates) are assembled into a
response and persisted as a `ScanRecord`.

### 4.2.2 Use Case Diagram (described)

Primary actor: the developer/analyst using the platform. Use cases: *Scan a pasted function*, *Scan a
batch of uploaded files*, *Scan a public GitHub repository*, *View per-function analysis*, *View
remediation recommendations*, *Apply an automated patch and re-scan*, *Explore a project's dependency
graph / call graph / knowledge graph*, *View scan history and export a report*, *Query the CI/CD
security-scan status*. All use cases route through the same FastAPI backend and, ultimately, the same
`ml_bridge` prediction path described in 4.2.1.

### 4.2.3 Activity Diagram (Scan → Analysis → Remediation → Re-scan, described)

Submit code → backend extracts features and predicts → result stored as a `ScanRecord` → user opens
Analysis page for that scan → user opens Recommendations page → if an automated patch is available and
safe to apply, user triggers *Apply & Re-scan* → backend creates a **new** `ScanRecord` with
`derived_from_scan_id` pointing back to the original, re-runs the full prediction pipeline on the
patched code, and returns a before/after comparison (verdict change, probability delta) — the
comparison is reported honestly even when the patch does not improve the score.

### 4.2.4 Database Design

The application persists to a local SQLite file (`backend/data/platform.db`) via SQLAlchemy, not a
full relational business schema — appropriate for its single-operator scope (Chapter 1.7). Two tables:

**`ScanRecord`** (table `scans`): `id`, `batch_id`, `project_name`, `filename`, `source`, `code`,
`verdict`, `vuln_probability`, `safe_probability`, `confidence`, `risk_level/tag/color`, `model_used`,
`is_demo`, `ast_features_json`, `metric_features_json`, `embedding_dims`/`embedding_2d_x`/
`embedding_2d_y`, `lines`, `loc`, `is_pinned`, `tags`, `derived_from_scan_id` (nullable, indexed — links
a re-scanned/patched record back to its origin), `created_at`.

**`GitHubBatchMeta`** (table `github_batch_meta`): per-batch repository provenance — `repo_url`,
`branch`, `commit_sha`, counts of files detected/analyzed/skipped, and skip reasons, so a GitHub scan's
UI can state exactly what was and was not covered rather than presenting a partial scan as complete.

A manual `_migrate_add_columns` routine handles adding `is_pinned`, `tags`, and `derived_from_scan_id`
to an already-existing database file, since SQLAlchemy's `create_all()` does not alter existing tables.

## 4.3 Input/Output Interface Design

### 4.3.1 User Interface (UI) Screens

The frontend (React 19 + TypeScript + Vite + Tailwind CSS v4, React Router v7) presents around 40
routed pages behind a persistent sidebar/topbar shell with a command palette (Ctrl/Cmd+K). The pages
most central to this report's scope:

- **Scanner** — three input modes (paste/edit via Monaco Editor, batch upload via drag-drop of
  files/folders/zip, and bundled examples), a classifier selector (XGBoost/Random Forest), and a result
  card (verdict, risk badge, probability bar, confidence, model used, a demo-mode warning banner when
  trained models are unavailable). See Figure 7.5 for a real scan result.
- **Analysis** — the per-scan deep-dive: verdict and confidence gauges, an "evidence-based risk" banner
  when a deterministic line-pattern scan disagrees with the model in the direction of *more* risk, a
  "Why This Verdict" panel, an approximate feature-contribution chart, an AST/metrics feature radar, a
  PCA scatter plot of the function's CodeBERT embedding against a background of training-set points,
  and a project-history trend chart. See Figure 7.6, and Figure 7.7 for the associated line-level
  heatmap with CWE tagging.
- **Recommendations** — a rule-based suggested secure rewrite (original vs. suggested diff), best
  -practice tip cards, and a separate, explicitly-labeled-heuristic "Performance & Efficiency
  Suggestions" section (loop-invariant calls, string growth in loops, heap allocation in loops, etc.)
  that is presented apart from the vulnerability score. See Figure 7.8 (rewrite) and Figure 7.9
  (performance panel with real findings).
- **AutoPatch** — detected vs. reference patch cards with a before/after diff viewer and, when a safe
  automated rewrite is possible, an "Apply & Re-scan" action that creates a linked derived scan and
  reports the honest before/after verdict comparison. See Figure 7.10.
- **DependencyGraph / CallGraphExplorer / KnowledgeGraph** — whole-project visualizations built with
  `@xyflow/react` and `dagre` layout: a file-level `#include` graph, a searchable cross-file
  function-call graph (with dangerous-call-chain highlighting), and a unified graph combining 11 node
  kinds (files, functions, CWE entries, dangerous APIs, pointers, buffers, predictions, etc.). See
  Figure 7.11 for a real cross-file call graph.
- **GitHubMode** — scans a public GitHub URL by shallow-cloning recent commits, scanning every file
  through the same pipeline, and deleting the local clone afterward; explicitly reports scan scope
  (files detected/analyzed/skipped and why).
- **PlatformHub (CI/CD tab)** — surfaces the same CI/CD pipeline described in Section 4.5 and
  `docs/CI_CD.md`, including a "run it locally" panel. See Figure 7.12 for a real GitHub Actions run of
  this pipeline.

### 4.3.2 API Design

The backend exposes a REST API under `/api`, registered as 17 routers in `backend/main.py` (route
groups: `scan`, `dashboard`, `history`, `analytics`, `knowledge`, `report`, `intelligence`, `system`,
`comparison`, `project`, `research`, `copilot`, `patches`, `export`, `watch`, `github`, `gamification`,
`search`), plus a health-check endpoint. Representative endpoints: `POST /api/scan/code` (single-function
scan), `POST /api/scan/batch` (multi-file scan), `POST /api/github/scan` (repository scan),
`GET /api/scan/{scan_id}/detail`, `POST /api/scan/{scan_id}/apply-patch`, `GET /api/project/{batch_id}/
dependency-graph`, `GET /api/project/{batch_id}/knowledge-graph`. CORS is configurable via the
`CORS_ALLOWED_ORIGINS` environment variable.

## 4.4 Module Description

### 4.4.1 Description of Each Module

**Table 4.1: Backend module responsibilities**

| Module | Responsibility |
|---|---|
| `app/predictor.py`, `app/utils.py` | Feature extraction (AST, metrics, CodeBERT) and model loading/inference — the shared core reused by both the offline pipeline and the live API |
| `backend/ml_bridge.py` | Bridges FastAPI to `app/`; adds presentation-only derived artifacts (AST viewer tree, line-risk scan, approximate contribution scores, PCA projection) |
| `backend/database.py` | SQLAlchemy models and manual migration logic for `ScanRecord` / `GitHubBatchMeta` |
| `backend/recommendations.py`, `rewrite_rules.py`, `patch_safety.py`, `auto_patch.py` | Rule-based remediation suggestion, safe-rewrite generation, and the apply-and-re-scan loop |
| `backend/repo_analysis.py`, `code_intelligence.py` | Whole-project dependency/call/knowledge-graph construction |
| `backend/github_service.py` | Shallow-clone, scan, and cleanup logic for public GitHub repositories |
| `backend/ci_scan.py` | The real pipeline invocation used by the GitHub Actions security-scan job |
| `backend/optimization_analyzer.py` | Heuristic performance/efficiency suggestion generation (explicitly separate from the vulnerability score) |

### 4.4.2 Functionality and Interaction

Every module above is reached only through the FastAPI routers, which in turn are the only callers of
`ml_bridge`; this keeps the ML core (`app/`) and the presentation-layer additions (heatmaps,
contribution scores, graphs) cleanly separated, so that a change to how the web application presents a
result never requires changing how the model itself is trained or how it computes a prediction.

## 4.5 CI/CD and Deployment Workflow

`docker-compose.yml` defines two services: `backend` (FastAPI, port 8000, a named volume for the SQLite
database, and a healthcheck with an extended ~200-second start period to tolerate the CodeBERT model's
cold load) and `frontend` (the built React app served by nginx on port 5173, proxying `/api/*` requests
to the backend). `.github/workflows/ci-cd.yml` runs four jobs on push/PR: `backend-validation` (compiles
and imports the FastAPI app, validates that the committed model artifacts load, runs the pytest suite),
`frontend-validation` (TypeScript build + Vitest), `security-scan` (runs the project's own real
CodeBERT/AST/metrics/XGBoost pipeline via `backend/ci_scan.py` against a pull request's changed files,
or the full repository on manual dispatch, uploading a SARIF report and posting a PR summary comment —
non-blocking by default), and `final-status` (aggregates a pass/fail summary).
