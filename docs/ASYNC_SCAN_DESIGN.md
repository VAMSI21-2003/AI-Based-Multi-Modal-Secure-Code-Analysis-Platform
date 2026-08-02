# Async Batch/GitHub Scan (Submit → Poll → Result) — Design (proposed)

**Status: proposed, not implemented.** Investigation-only per explicit
direction — report back and wait for sign-off before writing any
implementation code. Follows the same design-doc-first discipline as
`docs/APPLY_PATCH_LOOP_DESIGN.md`.

## 0. Why this matters — the correctness finding, not just UX

The most important result of this investigation isn't about speed or UX
polish. **`POST /api/scan/batch` currently freezes the entire backend for
every user, for the full duration of the scan (up to ~13 minutes on a
200-file repo) — not just the one request.** Full evidence in §2 below.
This makes the async refactor a correctness fix, not only a nicer UX.

## 1. Which endpoints are actually affected

Confirmed by reading the route handlers and their full call chains, not
assumed:

| Endpoint | Handler | Blocking? | Measured cost |
|---|---|---|---|
| `POST /api/scan/code` (paste) | `routers/scan.py:89`, plain `def` | No — single file, seconds | Stays as-is, out of scope |
| `POST /api/scan/live` (Monaco live) | `routers/scan.py:103`, plain `def` | No — debounced ~800ms | Stays as-is, out of scope |
| **`POST /api/scan/batch`** | `routers/scan.py:159`, **`async def`** | **Freezes the whole server** (§2) | **797.5s / 13.3 min for curl (200 files, `docs/PER_FUNCTION_INFERENCE_DESIGN.md:199-202`)** |
| **`POST /api/github/scan`** | `routers/github.py:22`, plain `def` | Occupies one threadpool slot, doesn't freeze the loop, but is still a single blocking HTTP request with no progress feedback | Clone (up to 90s) + same per-file cost as batch |
| `POST /api/watch/start` | `routers/watch.py:24`, plain `def` | Same synchronous-seed-scan issue as batch, up to 200 files | Related, **out of scope for this task** (see §7) |

Single-function paste/live scan is correctly left untouched — this design
only changes `scan_batch` and the GitHub scan endpoint.

## 2. Does a long scan block the event loop? — split answer, one is a real bug

**`POST /api/scan/batch`: yes, confirmed, with certainty.**

- It is the **only** `async def` route handler in the entire backend (grep
  confirmed — every other route is plain `def`).
- Its inference loop (`scan.py:225-233`) is a plain synchronous `for` loop
  with **zero `await` statements** inside it. The only `await` in the whole
  function is `await f.read()` (`scan.py:179`), which happens during upload
  ingestion, before scanning starts.
- There is **no offloading anywhere in this codebase** — grepped for
  `run_in_threadpool`, `to_thread`, `BackgroundTasks`, `ThreadPoolExecutor`,
  `run_in_executor`: zero matches in any `backend/*.py` file.
- Because it's `async def`, Starlette awaits it directly on the event loop
  instead of threadpooling it (that threadpooling only happens for plain
  `def` handlers). So for the full ~13 minutes, the one event-loop thread
  is stuck inside `scan.py`'s `for` loop running `torch` forward passes and
  `xgboost.predict_proba` — it cannot process *any* other request from
  *any* other user, including `/api/health`.
- Single uvicorn worker confirmed (`backend/Dockerfile:39`: no `--workers`
  flag; default is 1). No process-level parallelism to fall back on.
- Consequence, concretely: the Docker healthcheck (30s interval, 5s
  timeout, 3 retries) will mark the container **unhealthy** roughly 90
  seconds into any batch scan, and every other browser tab's
  `GlobalWatchNotifier` poll queues up unserved until the scan finishes.
- The frontend already has a comment (`frontend/src/api/client.ts:16-20`)
  naming this exact problem and exact fix as a known, deferred stopgap.

**`POST /api/github/scan`: no** — it's a plain `def`, so Starlette runs it
in the AnyIO threadpool automatically. The event loop stays free for other
users. It still occupies one of ~40 threadpool slots for its duration and
still gives the calling user zero progress feedback for up to 13 minutes,
which is the UX problem this task is also solving — but it is not the
server-wide freeze that `scan_batch` is.

**Practical implication for phasing**: converting `scan_batch` from
`async def` to a properly-offloaded submit/poll pattern fixes a real
correctness bug, not just UX. This alone would be worth prioritizing even
without the polling/progress UI, though the two are being built together
per the brief below.

## 3. Is the "watch" feature a reusable job-tracking mechanism?

**Its transport is directly reusable. Its state store is not.**

Reusable, and worth copying the shape of:
- The monotonic `seq` cursor + `GET /api/watch/{id}/events?since=N`
  incremental-delta protocol (`watch_service.py:239-244`,
  `routers/watch.py:55-67`) is a clean, already-shipped polling pattern.
- The frontend's adaptive-cadence global poller
  (`GlobalWatchNotifier.tsx`, 4s active / 30s idle, per-session cursor) is
  a ready-made pattern for a job-progress notifier — retargeting it from
  watch sessions to scan jobs is a small, mechanical change.
- Watch's actual scan work already runs off the request thread (on a
  `threading.Timer` thread with its own DB session,
  `watch_service.py:96-145`) — proof this codebase already has a working
  "fire work, return immediately, let a background thread finish it and
  update shared state" pattern, which is exactly what's needed here.

Not reusable — structurally a different thing, not just missing fields:
- Triggered by filesystem events (`watchdog.Observer`), an open-ended
  stream with no concept of "total work" or "done" — no `total`/
  `completed`/`percent` field exists anywhere in a watch session.
- Only two states ever (`"running"` / `"stopped"`) — no `queued`/
  `succeeded`/`failed`, no error field.
- State lives in a module-level Python dict (`_SESSIONS`,
  `watch_service.py:33`) — not durable across a restart, and would shard
  incorrectly under multiple uvicorn workers (not in use today, but worth
  designing around rather than repeating the same limitation).
- Bounded, lossy event buffer (`deque(maxlen=300)`) — fine for watch's
  per-file-change cadence, not safe to reuse verbatim for something with a
  known, larger total.

**Conclusion: reuse the *shapes* (cursor polling, adaptive frontend
cadence, off-thread execution), build a new, durable, terminal-state-aware
store rather than extending `_SESSIONS`.** Full reasoning in the
investigation notes; not repeating watch's own file changes here since
nothing in `watch_service.py` needs to change for this task.

## 4. CodeBERT batching — realistic headroom, not a hopeful one

**Honest answer: the async/progress change is the real win for the
*correctness and UX* problem. There is separately real, quantifiable
speed headroom in the inference code — but it's not in `BATCH_SIZE`, and
it touches `app/predictor.py`, which needs an explicit scope decision
(§8) given the "don't touch the ML/fusion pipeline" instruction for
Phase 2+.**

- `BATCH_SIZE = 16` (`app/predictor.py:294`) is **explicitly documented as
  untuned** — `docs/PER_FUNCTION_INFERENCE_DESIGN.md:164` calls it "a
  detail not fully specified in the design, added during implementation"
  purely to cap memory spikes. No benchmark, no throughput sweep, no
  measured memory usage exists anywhere for this value. There's no
  evidence it's near a real ceiling, but also no evidence raising it would
  help much — it hasn't been measured either way.
- **The real, quantified waste is the padding strategy**, not batch size:
  `predictor.py:329` uses `padding="max_length"`, padding every function
  to a full 512 tokens regardless of actual length. But the median
  function is **260 tokens** (`PER_FUNCTION_INFERENCE_DESIGN.md:188`) —
  roughly half of every batch's compute is spent on padding tokens that
  contribute nothing. Switching to `padding=True` (pad to longest-in-batch)
  should yield close to a **~2x** speedup on the CodeBERT stage, for
  functions under the truncation limit, with mathematically identical
  `[CLS]` output (the attention mask already excludes pad positions) —
  but this needs to be empirically verified against stored embeddings
  before shipping, since it changes what `app/predictor.py` computes.
- **A second, clearer win**: `scan_service.py:37` runs one *extra* whole-file
  CodeBERT forward pass per file, purely to compute a 2D PCA scatter
  coordinate for the Analysis Center chart — on top of the per-function
  passes already done for the verdict. On a 200-file repo that's 200 fully
  wasted forward passes. This doesn't change any inference *result*, only
  removes a redundant call — lower-risk than the padding change, but still
  touches `scan_service.py`'s call into `ml_bridge.py`.
- CPU-only throughout — no `cuda`/`torch.device`/GPU reference anywhere in
  `app/`. 125M-param model (`microsoft/codebert-base`), confirmed at
  `predictor.py:182`.
- Measured current throughput: ~2.4 functions/sec (1,896 functions in
  797.5s on curl) — batching already avoids roughly half of the naive
  unbatched overhead (`PER_FUNCTION_INFERENCE_DESIGN.md:208-211`
  documents this explicitly: 4.3x actual vs. ~9.5x naive expectation), so
  batching itself isn't the gap — the padding waste within each batch is.

**Bottom line, stated plainly, per your instruction not to give a hopeful
answer**: raising `BATCH_SIZE` alone is unlikely to move the needle much
and hasn't been measured. The dynamic-padding fix is real, quantifiable,
~2x headroom — but it's an ML-pipeline code change requiring embedding-
equivalence verification, and needs an explicit scope call given the "don't
touch ML/fusion pipeline" instruction (§8). The redundant-forward-pass
elimination is smaller but safer. **If neither speed optimization is
greenlit, the async/progress work alone is still worth doing** — it fixes
a real correctness bug (§2) and a real UX gap, independent of raw speed.

## 5. Data model: new `scan_jobs` table

Recommend a **new table**, not new columns on `scans` or `github_batch_meta`:

- **`scans` is one row per *file*, a job is one row per *submission*.**
  Extending `scans` would either duplicate job status across up to 200
  rows or have no row at all for a job with zero completed files yet.
  `ScanRecord` rows are only written *after* inference succeeds
  (`scan_service.py:69-71`) — there's no row to attach "queued"/"running"
  status to.
- **`github_batch_meta` is GitHub-only and write-once-at-completion**
  (`github_service.py:214-220`) — batch-upload and (later, if ever)
  watch jobs have no equivalent, and generalizing it means changing its
  write semantics from once-at-end to incremental, which is really a
  rewrite rather than an extension.
- **This matches the repo's own stated convention.**
  `GitHubBatchMeta`'s own docstring (`database.py:82-89`) explicitly
  argues for a new table specifically *because* ALTER TABLE on the
  already-populated `scans` table is treated as something to avoid where
  possible. A new `scan_jobs` table needs zero ALTER TABLE on `scans` —
  it's created fresh by the existing `Base.metadata.create_all()` call
  (`database.py:104`).

Proposed columns (String PK `batch_id`, reusing the existing `batch_id`
convention already indexed on `scans`, no FK — consistent with how
`batch_id`/`derived_from_scan_id` are already plain unconstrained lookup
columns on `scans`):

| Column | Type | Notes |
|---|---|---|
| `batch_id` | String | **PK** |
| `kind` | String | `"batch"` \| `"github"` |
| `status` | String | `"queued"` → `"running"` → `"succeeded"` \| `"failed"` |
| `files_total` | Integer | known once upload is decompressed / repo is cloned |
| `files_completed` | Integer | incremented per file as scanning proceeds |
| `files_failed` | Integer | invalid/skipped files |
| `error` | Text, nullable | set on `"failed"` |
| `result_json` | Text, nullable | the same aggregate payload `scan_batch` returns today, set on `"succeeded"` |
| `created_at` | DateTime | job submitted |
| `started_at` | DateTime, nullable | background work actually begins |
| `finished_at` | DateTime, nullable | terminal state reached |

`github_batch_meta` is **left exactly as-is** — still written once, at
completion, by the background worker, same as today. `scan_jobs` is a
separate, generic progress layer sitting in front of it; GitHub-specific
provenance (`repo_url`, `branch`, `commit_sha`, `skip_reasons`) stays where
it already lives.

### Execution mechanism: FastAPI `BackgroundTasks`, no new infra

Confirmed sufficient, per your instruction to justify or propose
otherwise:

- `BackgroundTasks.add_task(sync_fn, ...)` with a **synchronous** worker
  function runs that function via the same AnyIO threadpool plain `def`
  routes already use (`run_in_threadpool` under the hood) — it does *not*
  run on the event loop. This is the same offloading mechanism that
  already correctly keeps `POST /api/github/scan` off the event loop
  today, just invoked after the response is sent instead of before it.
- This also fixes `scan_batch`'s core bug for free: the route handler
  becomes plain `def` (or `async def` that only does quick, non-blocking
  setup before scheduling the background task and returning) with the
  actual scanning loop moved into the background task — off the event
  loop, matching the GitHub path's existing (correct) behavior.
- No Celery/Redis/message broker needed — matches the single-operator
  scope this project has consistently used elsewhere (SQLite, no queue
  infra anywhere else in the stack).
- **Known limitation, stated honestly rather than glossed over**: if the
  backend process restarts mid-job (container restart, `--reload` picking
  up a file change), that job silently stops with no crash record — its
  row stays at `"running"` forever. This is the **same risk profile Watch
  Mode already has today** (its `threading.Timer`-based execution has an
  identical failure mode) — not a new class of fragility introduced by
  this design. Cheap mitigation proposed: on server startup
  (`main.py`'s `lifespan`), mark any `scan_jobs` row still `"queued"`/
  `"running"` from a previous process as `"failed"` ("interrupted by
  server restart") — a few-line "reap orphaned jobs" step, not a durable
  job queue.

## 6. API contract

- **`POST /api/scan/batch`** — request body unchanged. Response changes
  from the full result payload to `{batch_id, status: "queued"}`
  (202 Accepted). Upload read + ZIP decompression still happen
  synchronously in the request (fast, and `files_total` needs to be known
  before returning) — only the per-file scanning loop moves to the
  background task.
- **`POST /api/github/scan`** — same shape change:
  `{batch_id, status: "queued"}` returned immediately; clone + per-file
  scanning happens in the background task. `_validate_url()`'s cheap
  synchronous checks stay in the request (fail fast on a bad URL rather
  than queuing a doomed job).
- **New: `GET /api/scan/jobs/{batch_id}`** — polled by the frontend.
  Returns:
  ```json
  {
    "batch_id": "...", "kind": "batch", "status": "running",
    "files_total": 117, "files_completed": 42, "files_failed": 1,
    "error": null,
    "created_at": "...", "started_at": "...", "finished_at": null,
    "result": null
  }
  ```
  When `status == "succeeded"`, `result` is populated with the same shape
  `scan_batch` returns synchronously today (so the frontend's existing
  result-rendering code needs minimal change). When `"failed"`, `error`
  is a human-readable message.
- `GET /api/scan/batches/list` (`scan.py:265`) is left as-is for this
  task — it's currently derived by `GROUP BY batch_id` on `scans` and
  only shows *completed* batches with rows; making it also show
  in-flight/failed jobs from `scan_jobs` would be a nice follow-up but
  isn't required for the submit→poll→result loop and is scope creep for
  this design (flagging it, not proposing it now).

## 7. Frontend changes

- Batch upload (Scan Center → Batch Upload) and GitHub Mode: submitting
  now gets back a `batch_id` almost immediately instead of waiting minutes
  for the full response.
- New polling loop, modeled directly on `WatchMode.tsx`'s existing
  `POLL_MS = 2000` `setInterval` pattern — poll
  `GET /api/scan/jobs/{batch_id}` every ~2s while `status` is `"queued"`
  or `"running"`, stop polling on `"succeeded"`/`"failed"`.
- **Real progress bar**, not a spinner: `files_completed / files_total`,
  matching the "42/117 files scanned" example in your brief — the data is
  directly available from the job row, no estimation needed.
- On `"succeeded"`, render `result` through the same components that
  already render `scan_batch`'s response today — the response shape is
  designed to match exactly, to minimize frontend churn.
- On `"failed"`, surface `error` plainly (matching this codebase's
  existing "show honestly, don't hide" convention from the Apply-Patch
  loop and elsewhere).
- `VITE_SCAN_TIMEOUT_MS` (currently 20 minutes, sized for the old blocking
  call) becomes mostly moot for the submit call itself, which returns in
  under a second — polling requests are individually fast and need only a
  normal short timeout. Worth a small follow-up cleanup, not core to this
  design.

## 8. Open questions for sign-off

1. **Confirm the `scan_jobs` table design (§5)** — new table, columns as
   listed, `github_batch_meta` left untouched.
2. **Confirm `BackgroundTasks` (no Celery/Redis) as the execution
   mechanism (§5)**, including the documented restart-loses-the-job
   limitation and the proposed cheap "reap orphaned jobs on startup"
   mitigation.
3. **Confirm the API contract (§6)** — `202`-style immediate response with
   `{batch_id, status}`, new `GET /api/scan/jobs/{batch_id}` polling
   endpoint, result shape mirrors today's synchronous response.
4. **Scope decision needed on the two real speed optimizations (§4)**,
   since both touch code that's part of the inference path and your
   Phase 2+ instructions say not to touch "the ML/fusion pipeline":
   - The dynamic-padding fix (`predictor.py:329`, ~2x on the CodeBERT
     stage, needs embedding-equivalence verification) — **in scope or
     deferred?**
   - The redundant whole-file forward pass removal
     (`scan_service.py:37`, used only for a PCA scatter coordinate) —
     lower risk, doesn't change any inference *result*, only removes a
     redundant call — **in scope or deferred?**
   - If both are deferred, the async/progress work (§§5-7) still stands
     on its own as a real correctness fix + UX improvement, per §4's
     honest bottom line.
5. **Confirm watch-mode's identical blocking issue (§1, `POST
   /api/watch/start`'s synchronous 200-file seed scan) is explicitly out
   of scope for this task** — flagged as a related finding, not proposed
   for this work.

Waiting for sign-off on the above before writing any implementation code.
