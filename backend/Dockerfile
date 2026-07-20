# =============================================================================
# backend/Dockerfile -- SecureCode AI API (FastAPI + the existing trained
# CodeBERT/AST/Metrics/XGBoost pipeline). Build context is the PROJECT ROOT
# (not backend/), since the backend imports app/ (the original pipeline) and
# models/ (the trained weights) as siblings of backend/.
#
#   docker build -f backend/Dockerfile -t securecode-ai-backend .
# =============================================================================

FROM python:3.11-slim

# git: required for GitHub Mode (git clone). build-essential: required to
# build a couple of native wheels (tokenizers, etc.) on some platforms.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# The existing, unmodified ML pipeline + trained weights.
COPY app/ ./app/
COPY models/ ./models/
# Needed for the contribution-baseline (mean/std) and dataset-stats endpoints
# (Research page). Optional at runtime -- those two panels degrade gracefully
# if absent -- but included by default for full functionality.
COPY dataset/processed/final_features.csv ./dataset/processed/final_features.csv
COPY dataset/processed/devign_cleaned.csv ./dataset/processed/devign_cleaned.csv

# The web API layer (this Phase 1-4 platform work).
COPY backend/ ./backend/

WORKDIR /srv/backend
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
