# Per-Function Live Inference — Design (not implemented)

Companion to Section A's CodeBERT-truncation investigation. **This is a
design/investigation report only — nothing described here has been built.**
It changes the live inference input path and needs explicit sign-off before
any code is written.

## 1. The problem, restated precisely

`ml_bridge.run_prediction(code, model)` is called with `code` = the entire
raw file for every batch/GitHub/folder scan (`routers/scan.py`,
`github_service.py`, `scan_service.py` all pass the full file text through
unchanged). `app/predictor.py` tokenizes that same string with
`max_length=512, truncation=True` for CodeBERT — identical settings to
training, but training's Devign rows are individual functions, not whole
files.

Measured on 150 real files sampled from real repos already scanned this
session (mbedTLS, libpng, zlib):

- **80% exceed 512 tokens** (vs. 45.5% measured on individual Devign
  functions in the training corpus)
- **Median file: 3,443 tokens** — CodeBERT sees roughly the first 15% of it
- **Largest sampled file: 168,837 tokens** — 330× over the limit

A second, previously undocumented consequence: `extract_ast_features` and
`extract_metric_features` are *also* called on the same whole-file string
today, not just CodeBERT. So live batch/GitHub scans compute all three
modalities — not only the embedding — at file granularity, while the model
was trained on function granularity. This is a training/inference
distribution mismatch beyond truncation alone.

## 2. Feasibility

High. The primitives already exist and are already proven in this
codebase:

- `code_intelligence.parse(code)` → tree-sitter `(root, source)`.
- `code_intelligence.find_functions(root)` → every `function_definition`
  node.
- Each function's exact source text is `source[node.start_byte:node.end_byte]`
  — the same slicing pattern already used to fix the Call Graph Explorer's
  duplicate-key bug this session.

No new parsing logic is needed — only a thin walker that calls these two
functions and slices out each function's text.

### Touch points (confirmed clean of the forbidden list)

`app/utils.py` (live extraction) and `src/ast/extract_ast_features.py`
(training extraction) are genuinely different files (different MD5
hashes). This redesign only touches the live-serving layer:
`app/predictor.py`, `backend/ml_bridge.py`, and the routers that call them
(`routers/scan.py`, `github_service.py`, `scan_service.py`). Nothing in
`src/ast/`, `src/metrics/`, `src/fusion/`, or `fusion_core.py` is involved,
and the 0.26 production threshold is unaffected (per-function verdicts
would still compare against the same threshold, just applied per function
instead of per file — see §3).

## 3. Aggregating per-function results into one file-level verdict

**Proposed: max risk across functions for the headline verdict, full
per-function breakdown carried alongside it — not averaged, not top-N.**

Reasoning:

- **Why not average**: diluting one genuinely vulnerable function's score
  across many safe ones in a large file *reduces* sensitivity — the wrong
  direction for a security tool. A 50-function file with one vulnerable
  function would report a low average score, hiding the real finding.
- **Why max, not some other reduction**: this mirrors a pattern already
  established and tested in this codebase —
  `ml_bridge.evidence_based_risk()` combines the ML score with deterministic
  line-evidence by taking the worse of the two, explicitly documented as
  "never suppress the model's own signal, only escalate." Reusing the same
  principle (worst signal wins) for per-function aggregation is consistent
  with how this platform already reasons about combining multiple risk
  signals, not a newly invented scheme.
- **Why also keep the full breakdown, not just the max**: collapsing to a
  single number would be strictly less informative than today's file-level
  score for zero benefit. Carrying `function_results: [...]` alongside the
  existing top-level fields is additive — the file-level verdict, risk
  level, and probability become "the worst function's values" (so existing
  UI consumers keep working unmodified), while a new UI surface (out of
  scope for this doc) could eventually show which specific function drove
  the verdict.

### Fallback for files with no detected functions

Headers with only declarations, or genuinely unparseable files: keep
today's whole-file behavior unchanged rather than silently skipping the
file or erroring.

## 4. Overhead on batch/GitHub scans — real numbers, not estimated

Functions-per-file measured on repos already scanned this session:

| Repo | Functions | Files | Ratio |
|---|---|---|---|
| zlib | 633 | 117 | 5.4 |
| mbedTLS | 1,185 | 133 | 8.9 |
| libpng | 1,467 | 101 | 14.5 |
| cJSON | 994 | 73 | 13.6 |

Roughly **5–15× more CodeBERT forward passes per file** (≈9× average).
Since CodeBERT dominates today's scan latency (186–249s measured for
200-file real repos), naive sequential per-function inference would push a
200-file scan toward 30–40+ minutes — past even the 10-minute
`VITE_SCAN_TIMEOUT_MS` stopgap added for Section A.

**This redesign is not viable without batched CodeBERT inference as a
companion change** (multiple functions in one forward pass — a standard,
well-supported `transformers` pattern, not naive sequential single-item
calls). This is a real implementation requirement to scope in up front, not
an optional optimization to consider later.

## 5. Response shape (additive, not breaking)

Existing top-level fields (`verdict`, `vuln_probability`, `risk_level`,
etc.) become "the worst function's values" — existing UI keeps working
without changes. A new `function_results: [...]` field carries the
per-function breakdown (name, line range, verdict, probability) for future
UI use, out of scope for this doc.

## 6. Shared infrastructure with Section G (optimization suggestions)

Directly reusable. The same "parse file → enumerate functions → get each
function's text + line range" walker this redesign needs is exactly what
`docs/OPTIMIZATION_SUGGESTIONS_DESIGN.md`'s heuristics want to reason
per-function over. Building this walker once, as a shared utility, avoids
two independent file-walkers doing the same tree-sitter traversal for two
different purposes.

## 7. Open questions for sign-off

1. Confirm max-risk aggregation (§3) is the right call, not a different
   reduction.
2. Confirm batched CodeBERT inference (§4) is accepted as a required,
   in-scope part of this work, not deferred — without it the overhead
   makes large-repo scans impractical.
3. Confirm the response-shape addition (§5) and where a per-function UI
   surface would eventually live (a new page, or an expansion of an
   existing one) — not designed here, since it's downstream of this
   decision, not a prerequisite for it.

---

## 8. Implementation notes (added after sign-off and implementation)

All three sign-off questions above were confirmed as designed and
implemented without deviation: max-risk aggregation (§3, unchanged),
batched CodeBERT inference (§4, implemented as required, not deferred),
and the additive `function_results`/`functions_analyzed` response fields
(§5, unchanged; a drill-down UI remains out of scope, deferred per
explicit direction this session).

### What was built, exactly

- `code_intelligence.extract_functions(code)` — the walker described in
  §2, built exactly as designed: `parse()` + `find_functions()`, no new
  parsing logic. Returns `[]` for files with no functions, confirmed via
  tests to correctly fall back to the original whole-code path.
- `app/predictor.py`: `extract_codebert_embeddings_batch()` (chunked at
  `BATCH_SIZE = 16` — a detail not fully specified in the design, added
  during implementation so one pathological file with hundreds of
  functions can't spike memory in a single forward pass) and
  `predict_functions_with_model()` (per-function AST/metrics/classifier,
  reusing the batched embeddings).
- `backend/ml_bridge.py`: `run_prediction()` now calls
  `_predict_per_function_or_whole()`, which does the split → batch-embed →
  classify-per-function → max-aggregate sequence, then carries the full
  breakdown in `function_results`.
- Touches confirmed to stay clear of the forbidden list, as designed:
  only `app/predictor.py`, `backend/ml_bridge.py`,
  `backend/code_intelligence.py`. Nothing in `src/ast/`, `src/metrics/`,
  `src/fusion/`, `fusion_core.py`, the 0.26 threshold, or any trained
  model file was touched.

### Real before/after numbers (not estimated)

**Truncation rate** — re-measured on the same 150-file real-repo sample
(mbedTLS, libpng, zlib) used for the original whole-file measurement:

| | Before (whole-file) | After (per-function) |
|---|---|---|
| Truncation rate | **80%** of files | **30.1%** of functions |
| Sample size | 150 files | 1,544 functions (from the same 150 files; 52 of the 150 files had no function bodies to split — header-only files, correctly fell back to whole-code) |
| Median | 3,443 tokens/file | 260 tokens/function |

30.1% is *better* than the 45.5% training-corpus baseline cited as the
target in §1 — real-world repo functions (this sample) skew shorter on
average than Devign's commit-diff-selected training functions, which was
not something the design predicted either way but is a plausible,
measured explanation, not assumed.

**Scan duration** — fresh live re-scans through the real GitHub-scan
endpoint (not simulated), server-measured `scan_duration_sec`:

| Repo | Files | Functions | Before | After | Per-file ratio |
|---|---|---|---|---|---|
| **curl** (clean comparison — same 200 files, same `master` branch both times) | 200 | 1,896 | 186.1s | **797.5s** | **~4.3x** |
| zlib (caveated — see below) | 67 (this run; 117 in the original measurement) | 492 | 103.3s (117 files) | 207.6s (67 files) | ~3.5x |

**curl is the clean, controlled comparison**: identical file count (200)
and branch (`master`) both times, so the ~4.3x per-file slowdown is a
direct, uncontaminated measurement of the redesign's real cost — not
inflated or deflated by a differing file set. Its function-to-file ratio
was 1,896/200 ≈ 9.5; the naive (unbatched, sequential) expectation from
§4 would be roughly that same ~9.5x, so batching measurably delivered
**less than half** the naive overhead (4.3x actual vs. ~9.5x naive) —
confirming real savings, not just the theoretical possibility of them.

**zlib caveat**: the fresh re-scan resolved 67 files on branch `develop`,
not the 117 files the original whole-file measurement covered (an
uncontrolled difference, likely default-branch resolution — not pinned
down further). Its ~3.5x per-file ratio is directionally consistent with
curl's cleaner ~4.3x but shouldn't be over-weighted given the mismatched
file set.

**Bottom line, stated plainly**: batching keeps this practical relative to
the naive alternative (roughly half the overhead, not the full 5-15x),
but it is **not free** — curl's real scan time went from 186s to 797.5s
(~13.3 minutes), which is now **past the 10-minute `VITE_SCAN_TIMEOUT_MS`
stopgap added in Section A**. That stopgap was sized against whole-file
scan times measured before this redesign; it has not been re-tuned for
per-function scan times, and this real measurement shows it needs to be —
flagged here rather than silently left inconsistent with the new reality
this same session introduced.

**Scope of what was actually re-measured**: 2 of the 6 repos originally
listed (curl and zlib) were re-scanned fresh this session, not all 6 —
each real scan takes several minutes to over 13 minutes, and curl's clean,
controlled result is sufficient to establish the real overhead ratio.
Reported honestly rather than extrapolating unmeasured numbers for
mbedTLS, sqlite, busybox, or wolfSSL.

### Follow-up this measurement surfaced (not actioned this session)

`VITE_SCAN_TIMEOUT_MS` (`frontend/.env.example`, currently 600000ms/10min)
should be reconsidered now that a real 200-file repo measured at 797.5s
server-side — the client-side timeout needs to account for per-function
scan times, not the whole-file times it was originally sized against.
Not changed as part of this implementation session since it's a separate,
narrowly-scoped follow-up, not part of the per-function redesign itself —
flagging it here so it isn't lost.

