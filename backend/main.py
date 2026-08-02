# =============================================================================
# main.py -- FastAPI application entry point.
#
# Reuses the EXISTING trained ML pipeline (app/predictor.py, app/utils.py,
# models/xgboost.json, models/random_forest.joblib) via ml_bridge.py.
# This file only wires up the web API layer around it.
#
# Run:  uvicorn main:app --reload --port 8000   (from the backend/ directory)
# =============================================================================

import os
import sys
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logging_config import setup_logging
setup_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import scan, dashboard, history, analytics, knowledge, report, intelligence, system, comparison, project, research, copilot as copilot_router, patches, export, watch, github, gamification, search
import job_service
import ml_bridge


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm CodeBERT + XGBoost + Random Forest at startup rather than
    # lazily on first request. Without this, whichever endpoint happens to
    # touch the models first (a scan, the Research page, Live IDE, ...) pays
    # a 15-30s cold-start cost with no explanation beyond a generic spinner.
    ml_bridge.get_xgb_model()
    ml_bridge.get_rf_model()
    ml_bridge.get_codebert()

    # Async batch/GitHub scan jobs (docs/ASYNC_SCAN_DESIGN.md) run via
    # BackgroundTasks, in-process -- if this process restarted while a job
    # was mid-flight (container restart, --reload picking up a file
    # change), that job's row is orphaned at "queued"/"running" forever,
    # since nothing will ever update it again. Reap them once at startup.
    reaped = job_service.reap_orphaned_jobs()
    if reaped:
        print(f"[startup] Marked {reaped} orphaned scan job(s) as failed (interrupted by restart).")

    yield


app = FastAPI(
    title="AI Secure Code Analysis Platform API",
    version="1.0.0",
    description="API layer around the existing CodeBERT + AST + Metrics + XGBoost vulnerability detection pipeline.",
    lifespan=lifespan,
)

# Comma-separated list, e.g. "http://localhost:5173,https://scan.example.com".
# Falls back to the dev-server/Docker defaults (frontend/vite.config.ts's dev
# server and docker-compose.yml's frontend port both use 5173) if unset, so
# behavior is unchanged for anyone not explicitly configuring this.
_cors_env = os.environ.get("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOWED_ORIGINS = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else ["http://localhost:5173", "http://127.0.0.1:5173"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router)
app.include_router(dashboard.router)
app.include_router(history.router)
app.include_router(analytics.router)
app.include_router(knowledge.router)
app.include_router(report.router)
app.include_router(intelligence.router)
app.include_router(system.router)
app.include_router(comparison.router)
app.include_router(project.router)
app.include_router(research.router)
app.include_router(copilot_router.router)
app.include_router(patches.router)
app.include_router(export.router)
app.include_router(watch.router)
app.include_router(github.router)
app.include_router(gamification.router)
app.include_router(search.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
