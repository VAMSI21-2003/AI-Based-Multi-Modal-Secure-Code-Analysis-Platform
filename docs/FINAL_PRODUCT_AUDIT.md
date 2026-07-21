# Final Product Audit (Phase A)

Read-only, evidence-based audit — every row below is backed by a specific
file/line, either re-verified in this pass or carried forward from prior
sessions' equally-verified work (ML pipeline, tests, CI/CD, SonarQube
removal). Nothing here is assumed from a prior summary without re-checking
the actual code. One specific claim in this session's brief — "the UI
visually suggests folder upload but only accepts individual files" — was
investigated in depth and **found to be false**; see §2 for the evidence.
That doesn't mean everything is fine — real gaps were found elsewhere, and
they're reported just as plainly.

## 1. Feature status table

| Feature | UI exists | Backend exists | Actually works | Real ML | Tested | Performance | Status |
|---|---|---|---|---|---|---|---|
| Single-file paste scan | Yes | Yes (`/api/scan/code`) | Yes | Yes (XGBoost/RF) | Yes | Fast (<1s post-warmup) | **A — fully functional** |
| Multi-file batch upload | Yes | Yes (`/api/scan/batch`) | Yes | Yes | Partial (no dedicated batch-upload test) | Untested at scale | **A/B — functional, undertested** |
| **Folder upload** | Yes (`webkitdirectory`) | Yes (relative path preserved end-to-end) | **Yes, genuinely** | Yes | No dedicated test | Untested | **A — functional, contrary to the brief's suspicion** (see §2) |
| ZIP upload | Yes (same endpoint, by extension) | Yes (in-memory `zipfile`, no disk extraction) | Yes | Yes | No dedicated test | Untested | **A/B — functional; no explicit Zip Slip guard, but inert since nothing is extracted to disk** |
| GitHub repo scan | Yes | Yes (`github_service.py`) | Yes | Yes | Yes (URL validation tests) | Measured (~68s/67 files) | **A — fully functional** |
| Discovered/ignored file breakdown in UI | **No** | Yes for GitHub (files_detected/analyzed/skipped/skip_reasons), no for batch upload | Backend computes it (GitHub only), **UI never shows it anywhere** | n/a | n/a | n/a | **J — misleading by omission**: the exact data Phase 2 wants is already computed server-side for GitHub scans and simply never rendered |
| Dashboard / Project Summary | Yes | Yes | Yes | Yes | Partial | **Slow — recomputes on every request** | **I — real functional bug**: see §3 |
| AST structural analysis | Yes (viewer) | Yes (tree-sitter-c) | Yes | n/a (deterministic) | Yes (11-dim shape test) | Fast | **A** |
| Software metrics | Yes | Yes | Yes | n/a (deterministic) | Yes (13-dim shape test) | Fast | **A** |
| CodeBERT embedding | Partial (dims shown) | Yes | Yes | Yes | Yes (fusion-shape test) | Slow (~1-3s/function, dominates scan time) | **A, with a known limitation**: 45.5% of functions truncated at 512 tokens (measured, `docs/ML_PIPELINE.md`) |
| Multi-modal fusion | Yes (explained) | Yes (792-dim vector) | Yes | Yes | Yes (order/shape test) | Fast | **A** |
| Risk probability + verdict | Yes | Yes | Yes | Yes | Yes (determinism + threshold tests) | Fast | **A** — threshold tuned to 0.32 via validated experiment, applied live |
| Code-level explainability (AST/metric evidence, insights) | Yes | Yes (`describe_features`, `line_risk_scan`, `code_intelligence.analyze`) | Yes, genuinely deterministic | Partial (evidence is heuristic/deterministic, not model-attribution beyond approximate feature contributions) | No dedicated test | Recomputed per-request in aggregation endpoints (see §3) | **A/F — real, but framed inconsistently as "AI insight" in places vs. clearly-labeled heuristic elsewhere** (needs a wording pass, not new logic) |
| Auto-Patch / remediation engine (`auto_patch.py`) | Yes (`AutoPatch.tsx`) | Yes | Yes, genuinely rule-based (regex-pattern matched: strcpy/gets/sprintf/scanf/double-free/integer-overflow) | No (deterministic by design — correctly NOT ML) | No dedicated test | Fast | **A/C — real for the ~6 patterns it covers; explicitly and honestly falls back to "reference/canonical" cards for everything else, never fabricates a fix** |
| Re-scan-after-patch verification | **No** | **No** | **Not implemented** | n/a | n/a | n/a | **D/H — missing entirely.** The patch UI shows before/after + explanation but has no "apply patch → re-scan → compare risk" loop. This is a real gap against the explicit "re-scan is mandatory" requirement. |
| Code Explanation page | Yes | Yes | Yes | Partial | No | Fast | **A** |
| GitHub Actions CI/CD | Yes (docs) | Yes | Yes | Yes (real scan of a demo fixture) | n/a | Fast (~2-3 min pipeline) | **A, honestly scoped**: `docs/CI_CD.md` already discloses it scans `demo/scan_samples/` (2 files), not the whole repo, and why |
| SonarQube comparison (embedded) | **Removed** | **Removed** | n/a | n/a | n/a | n/a | **Correctly removed** in a prior pass — verified again this session via `git status`/grep: no `SonarQubeComparison.tsx`, `LiveRepoComparison.tsx`, `platform_comparison.py`, or `live_comparison.py` exist |
| Commit SHA / branch / scan-scope tracking (GitHub Mode) | Partial (backend has it, UI doesn't surface all of it) | Yes (`github_batch_meta` table, survives restart) | Yes | n/a | Yes (5 tests) | Fast | **A/J — real and tested, but under-surfaced in the UI** (same gap as the discovered/ignored breakdown) |
| Test suite | n/a | n/a | 22 backend tests, 9 frontend tests, all real-behavior (determinism, fusion shape, URL validation, error handling, component rendering) | n/a | — | Full suite ~25s backend / ~8s frontend | **A** |

## 2. Folder/ZIP upload — the specific claim, verified false

Traced end-to-end:

- `frontend/src/pages/Scanner.tsx:257` — the "Choose Folder" `<input type="file">` genuinely carries `webkitdirectory="true" directory="true"`, not a cosmetic label.
- `Scanner.tsx:270` and `frontend/src/api/client.ts` (`scanBatch`) both read `(f as any).webkitRelativePath || f.name` — folder structure is read and sent, not discarded.
- `backend/routers/scan.py`'s `/api/scan/batch` receives each `UploadFile.filename` verbatim (the relative path arrives as the multipart filename) and stores it in `ScanRecord.filename`.
- Downstream consumers (`FileExplorer.tsx`'s tree builder, `project.py`'s folder/knowledge-graph builders) split that stored filename on `/`/`\` to reconstruct the folder tree — and this only works *because* the path survived intact.
- ZIP upload (same endpoint, dispatched by `.zip` extension) reads `zf.infolist()[].filename`, which also preserves internal archive paths.

**Conclusion: folder and ZIP upload both genuinely preserve and use relative paths end-to-end.** The real gaps are elsewhere (see row above: no discovered/ignored breakdown shown; no dedicated Zip Slip normalization, though inert since nothing is written to disk).

## 3. Dashboard/aggregation performance — confirmed real bug

`backend/routers/project.py`:
- `project_summary()` (lines 30–127): for every `ScanRecord` in the batch, on **every single call**, re-runs `code_intelligence.analyze(r.code, ...)` (full AST parse + dangerous-API scan + code-smell detection) **and** `ml_bridge.line_risk_scan(r.code)` (a second full pass) — both from scratch, with zero caching or persistence of the results.
- The identical pattern repeats in `dependency_graph()` (line ~216) and `knowledge_graph()` (line ~344) in the same file.
- No `ScanRecord` column stores these derived values; no `@lru_cache` or similar exists on `code_intelligence.analyze`/`ml_bridge.line_risk_scan`.
- This directly explains the ~8-second dashboard load observed live in browser testing for a 67-file GitHub batch earlier this session (partially misattributed at the time to a `useCountUp` animation artifact — the animation is real too, but the dominant cost is this per-request recomputation).

**This is the single highest-value functional fix identified in this audit.**

## 4. What was NOT re-audited this pass (carried forward, already verified in prior sessions)

- ML pipeline forensic audit (data leakage bound, near-duplicate label noise, class imbalance handling, threshold tuning) — `docs/ML_PIPELINE.md`, `docs/ML_EXPERIMENTS.md`.
- SonarQube UI removal — re-confirmed via `git status` this session, not re-derived.
- Test suite composition — re-run this session (22/9 passing), not newly written.
- CI/CD scope and honesty — `docs/CI_CD.md`, unchanged and still accurate.

## 5. Prioritized plan for Phases B–M

Given what's real vs. gaps found:

| Order | Phase | Why this order |
|---|---|---|
| 1 | **C — dashboard/aggregation caching** (not B) | The single highest-impact, best-understood, lowest-risk fix (§3). Moving it ahead of the (already-mostly-done) SonarQube-removal re-check avoids leaving a known, reproducible performance bug live any longer than necessary. |
| 2 | **B — re-verify SonarQube-comparison removal is still clean** | Already done; a quick re-confirmation (grep + `git status` + build) rather than redoing the removal itself. |
| 3 | **Surface discovered/ignored file counts in the UI** (part of the original Phase 2 ask) | Folder/ZIP upload itself doesn't need fixing (§2), but the missing discovered/supported/ignored breakdown is real and cheap to add — the backend data for GitHub Mode already exists and just needs rendering; batch upload needs the same counts computed and returned. |
| 4 | **Re-scan-after-patch loop for Auto-Patch** | The single most important missing *product* capability (§1) — directly matches the explicit "re-scan is mandatory" rule. |
| 5 | **E/F/G — remaining ML work**: long-function CodeBERT strategy experiment, model comparison with cross-validation, calibration/operating-mode exposure | Already substantially audited; this is new experimental work, appropriately sequenced after the cheaper product fixes above. |
| 6 | **H — explainability wording pass** | Ensure "AI insight"-style labels never overstate what is actually a deterministic heuristic (§1) — a documentation/labeling fix, not new logic. |
| 7 | **J — platform security audit** | Zip Slip normalization (defensive, currently inert-but-cheap to fix), plus the fuller checklist (CORS, path traversal, command injection, secrets, temp-file cleanup). |
| 8 | **K — CI/CD** | Already honestly scoped; only touch if Phase 1-4 changes affect it. |
| 9 | **L — end-to-end validation** | After all of the above. |
| 10 | **M — manual SonarQube comparison doc** | Last, as instructed — documentation only, no product changes. |

Stopping here per your instruction — no code has been modified in this response. Confirm this plan (or redirect it) and I'll proceed into Phase 1 (dashboard caching) next.
