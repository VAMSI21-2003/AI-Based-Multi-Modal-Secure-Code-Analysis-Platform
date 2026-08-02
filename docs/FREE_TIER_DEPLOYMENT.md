# Free-Tier Deployment (Vercel + Render)

Frontend on Vercel (static React/Vite build), backend on Render's free web
service tier (Docker, 512MB RAM). The backend runs in **fallback/heuristic
mode** by design: CodeBERT is not loaded, so verdicts come from the real
trained XGBoost/Random Forest classifiers running on AST + Metrics features
only (CodeBERT's 768 dims filled with zeros). This is an accepted tradeoff
for a free deployment, not a bug.

## 1. Memory footprint: measured, not estimated

Ran the actual backend model-load sequence under `psutil`, then re-verified
end-to-end inside the real Docker image with Docker's own `--memory` cap
enforced (closest local proxy to Render's hard limit):

| Scenario | RSS |
|---|---|
| XGBoost + Random Forest loaded, no torch/transformers imported, in a bare venv | 346.8 MB |
| Same, **plus CodeBERT** (torch+transformers imported, 125M-param model loaded) | 835.2 MB |
| **Real `backend/Dockerfile.render` image, running under `docker run --memory=512m --memory-swap=512m`, after startup + a real scan request** | **394.8 MB (77% of the 512MB cap)** |

Container log on startup confirms the graceful-degradation path is exactly
what's expected, not a crash:
```
WARNING  predictor: Could not load CodeBERT: No module named 'torch'
INFO:    Application startup complete.
```

A real scan through the capped container (`POST /api/scan/code`) returned:
```json
{"verdict": "VULNERABLE", "vuln_probability": 53.31, "model_used": "XGBoost", "is_demo": false}
```
**Be precise about what this does and does not prove.** CodeBERT was never
loaded and never ran — `torch` was never installed in this image (excluded
from `requirements-lite.txt` on purpose; this is not a memory optimization
that made CodeBERT fit, there isn't one). `is_demo: false` means the real
*trained XGBoost classifier* ran — as opposed to `demo_predict()`'s
separate, pure regex-heuristic path — but its input was real AST + Metrics
features with CodeBERT's 768-dim embedding slot filled with **zeros**, not
a real semantic embedding. Internally `app/predictor.py` labels this
`embedding_source: "Zero vector (CodeBERT not loaded)"`. So: a real
classifier, on a real-but-degraded feature vector. It is not, and was never
claimed to be, CodeBERT-based inference. This is `app/predictor.py`'s
existing, pre-built fallback path (`load_codebert_components()`'s `except
Exception` catches the `ModuleNotFoundError` and returns `(None, None)`;
every downstream caller already checks for that and degrades). **Zero
application code changes were needed** for this — only the
requirements/Dockerfile excluded torch/transformers.

The original `backend/Dockerfile` (with CodeBERT) would exceed the 512MB
cap by ~60% and get OOM-killed by Render — confirmed by the 835.2MB
in-process measurement above; not re-tested against the hard cap since an
OOM kill under `--memory=512m` was not worth reproducing on purpose.

## 2. SQLite persistence: ephemeral, plainly stated

Render's free web service tier has **no persistent disk** (a paid-tier add-
on) and free instances also **spin down after ~15 min idle**, cold-starting
into a fresh container on the next request. `backend/data/platform.db` is
created at runtime inside the container's writable layer, not baked into
the image.

**Practical effect: scan history resets on every redeploy AND on every
cold-start-after-idle cycle** — for a mostly-idle demo deployment, that
likely means every session, not just occasional redeploys. This is expected
and fine for a demo; there is no way to make it durable without a paid
Render disk.

## 3. CORS / split-origin changes

- **Backend**: already env-var driven. `backend/main.py` reads
  `CORS_ALLOWED_ORIGINS` (comma-separated), defaulting to the dev-server
  origins if unset. `render.yaml` sets this to the deployed Vercel URL.
- **Frontend**: `frontend/src/api/client.ts` used a relative `baseURL: "/api"`
  plus 11 hardcoded `` `/api/...` `` download-link builder functions
  (`downloadScanPdf`, `downloadExecutivePdf`, etc.) — this worked only
  because Docker's nginx (`frontend/nginx.conf`) and the Vite dev server
  (`vite.config.ts`) both reverse-proxy `/api/*` to the backend on the same
  origin. Vercel's static hosting has no such proxy to a Render backend on
  a different origin. **Real code change made**: added a
  `VITE_API_BASE_URL` build-time env var, prefixed onto the axios
  `baseURL` and all 11 download-URL builders, defaulting to `""` (empty
  string) when unset — dev/Docker Compose behavior is unchanged byte-for-
  byte when the var isn't set. Verified: `npx tsc -b` clean, `npm run build`
  clean, `npm run test` 9/9 passing after the change.

## 4. What changed / what's new

New files (none touch `backend/Dockerfile`, `docker-compose.yml`, or any
existing dev/Docker Compose behavior — all additive):

- `backend/requirements-lite.txt` — `requirements.txt` minus `torch`/`transformers`.
- `backend/Dockerfile.render` — uses the lite requirements; does not copy
  `dataset/processed/final_features.csv` (243MB) or `devign_cleaned.csv`
  (54MB) into the image. Both files' only consumers
  (`ml_bridge._feature_baseline()`, `analytics._dataset_stats_cached()`)
  already check `os.path.exists()` and return "not available" if missing —
  confirmed by reading both call sites, not assumed. Those two CSVs were
  pure image bloat and a latent memory risk on the free tier for two
  optional Research/Analytics panels.
- `render.yaml` — Docker web service, `plan: free`, `healthCheckPath:
  /api/health`, `CORS_ALLOWED_ORIGINS` env var (placeholder, must be set to
  the real Vercel URL after the frontend is deployed).
- `frontend/vercel.json` — build config (`npm run build` → `dist`) plus a
  SPA catch-all rewrite to `index.html`, matching `nginx.conf`'s existing
  `try_files ... /index.html` behavior (React Router needs this on static
  hosting or direct navigation to any non-root route 404s).
- `frontend/.env.example` — documents the new `VITE_API_BASE_URL` var.

## 5. Deploy steps (manual, dashboard-driven — no CLI credentials available in this environment)

1. **Render**: dashboard → New → Blueprint → connect this GitHub repo → it
   reads `render.yaml` and creates the service automatically. Note the
   assigned `https://<name>.onrender.com` URL once live.
2. **Vercel**: dashboard → New Project → connect this repo → set **Root
   Directory** to `frontend` → set env var `VITE_API_BASE_URL` to the
   Render URL from step 1 (no trailing slash) → deploy. Note the assigned
   `https://<project>.vercel.app` URL.
3. **Back to Render**: update the `CORS_ALLOWED_ORIGINS` env var on the
   backend service to the real Vercel URL from step 2, and redeploy (or
   edit `render.yaml`'s placeholder and push, since Render blueprints
   re-sync from the repo).
4. Confirm end-to-end: load the Vercel URL, submit a real scan, confirm it
   completes and shows `model_used: XGBoost` / `is_demo: false` (fallback
   mode, not the pure-heuristic demo path).

## 6. Reproducing the local verification

```bash
docker build -f backend/Dockerfile.render -t securecode-ai-backend-lite .
docker run -d --name lite-test --memory=512m --memory-swap=512m -p 8001:8000 securecode-ai-backend-lite
curl http://localhost:8001/api/health
docker stats lite-test --no-stream
docker rm -f lite-test
```

## 7. Live deployment record

- Backend:  https://securecode-ai-backend.onrender.com
- Frontend: https://securecode-ai.vercel.app
- Repo:     https://github.com/VAMSI21-2003/AI-Based-Multi-Modal-Secure-Code-Analysis-Platform

Live end-to-end verification (real requests against the actual deployed
services, not a local reproduction):

- `GET /api/health` → `{"status":"ok"}`, 200, 0.82s (backend already warm).
- `POST /api/scan/code` direct against the live backend → 200, 0.29s,
  `verdict: VULNERABLE`, `vuln_probability: 53.31`, `model_used: XGBoost`,
  `is_demo: false`.
- `GET /api/system/stats` on the live backend → `process_ram_mb: 328.8`
  (real live RSS, consistent with the fallback measurements in §1, nowhere
  near the ~700-800MB CodeBERT would need) and
  `model_load_times_sec.codebert: 0.001` (an instant failed import, not a
  real multi-second weight load) — independent confirmation the live
  deployment is genuinely in fallback mode, not just claiming to be.
- Same scan submitted through the real browser UI at the Vercel URL:
  identical result rendered (VULNERABLE / MEDIUM RISK / 53.3% / XGBoost).
  Network tab confirmed `POST https://securecode-ai-backend.onrender.com/api/scan/code`
  → 200, made cross-origin from the Vercel domain — only possible if CORS
  is genuinely configured correctly, since the browser blocks the request
  client-side otherwise. Zero console errors.

### Fallback-mode disclosure banner

Since `is_demo: false` alone could be misread as "full model" when this
deployment is actually running real XGBoost on a degraded (CodeBERT-zeroed)
feature vector, the Scanner and Analysis pages show a visible banner
("Running in reduced-accuracy mode: semantic (CodeBERT) analysis is
unavailable on this free-tier deployment...") whenever that's genuinely
true. The signal is authoritative and server-side, not guessed client-side:
`backend/system_monitor.py` records whether `ml_bridge.get_codebert()`
actually returned a real tokenizer/model the one time it runs (at startup,
via `lifespan()`), and `GET /api/health` exposes it as
`codebert_available: true | false | null` (`null` only if that resolution
genuinely hasn't happened yet in-process, which never occurs against a
running deployed app). The frontend (`frontend/src/api/client.ts`'s
`getHealth()`) fetches this once per page load on Scanner and Analysis, and
renders the banner only on an explicit `=== false`, never on a falsy/null
value — so it can't false-positive while the check is still in flight.
