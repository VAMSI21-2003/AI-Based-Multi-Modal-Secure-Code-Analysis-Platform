# Running SecureCode AI with Docker

One command brings up the whole platform -- backend API, web dashboard, and
a persistent database:

```bash
docker compose up --build
```

- Dashboard: http://localhost:5173
- API + Swagger docs: http://localhost:8000/docs

Stop everything with `docker compose down` (add `-v` to also delete the
database volume and start fresh).

## What's in each container

| Service | Image | What it runs |
|---|---|---|
| `backend` | `python:3.11-slim` | FastAPI + the existing trained CodeBERT/AST/Metrics/XGBoost pipeline (unchanged) |
| `frontend` | `node:20-slim` (build) → `nginx:1.27-alpine` (serve) | The built React dashboard, with nginx proxying `/api/*` to the backend container |

## Database

The platform's database is SQLite (`backend/data/platform.db`) -- this was
already the case before Docker support was added, and this Dockerfile setup
does not introduce a different database engine (that would be a rewrite of
`backend/database.py`, which is out of scope). The file lives in the named
volume `scan_data`, so scan history survives `docker compose down` /
`docker compose up` cycles. Delete it with `docker compose down -v` if you
want a clean slate.

## Build context note

`backend/Dockerfile` is built from the **project root** (not `backend/`),
because the backend imports `app/` (the original CodeBERT/AST/Metrics
pipeline) and `models/` (the trained weights) as siblings of `backend/`.
`docker-compose.yml` already points at the right context -- if you build the
backend image manually, do it from the project root:

```bash
docker build -f backend/Dockerfile -t securecode-ai-backend .
```

## Image size

The backend image bundles `torch` + `transformers` (for CodeBERT) plus two
CSV files from `dataset/processed/` (`final_features.csv`,
`devign_cleaned.csv` -- used by the contribution-baseline and dataset-stats
panels on the Research page). Expect a multi-GB image; this is inherent to
shipping the real trained pipeline, not something Docker-specific work can
shrink without removing functionality.

## Rebuilding after code changes

```bash
docker compose up --build backend    # after editing anything in backend/ or app/
docker compose up --build frontend   # after editing anything in frontend/src
```
