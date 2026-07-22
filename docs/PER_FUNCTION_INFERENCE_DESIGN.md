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
