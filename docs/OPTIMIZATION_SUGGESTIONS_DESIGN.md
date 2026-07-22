# Optimization Suggestions — Phase 1 Design (implemented, Phase 2 complete)

**Status: implemented.** Design signed off as written (all 5 checks in
§1.1–1.5, §1.6's exclusion, the Recommendations.tsx placement in §3, and
the analysis_cache lazy-integration point in §2) — no changes to scope
during implementation. A new, separate, clearly-labeled capability
alongside the existing security vulnerability detection.

**Critical boundary, restated and honored throughout this design:** this
must never be merged into the ML risk score or presented as ML-derived.
Every check below is deterministic (tree-sitter/regex), the same
architectural class as `code_intelligence.py`'s existing dangerous-API
detector — not a variant of the trained classifier. Findings must be
labeled `"heuristic-based"` in both the API response and the UI, matching
the honesty standard this codebase already applies to `model_mode`
("trained"/"fallback").

## 0. First: what already exists, so this doesn't duplicate it

`code_intelligence.py::analyze_code_smells()` **already ships today** and
is **already surfaced in the UI** (`AdvancedAnalysis.tsx`), covering:
unused variables, **unreachable code after return/break/continue**,
shadow variables, long parameter lists, large functions (>50 LOC), deep
nesting (≥5), magic numbers, duplicate lines.

This matters directly: "unreachable code after a return," one of the
example checks in the original brief, is not a gap — it's already built.
The checks proposed below were chosen to be genuinely new: **performance/
efficiency** issues, not the maintainability/style smells `code_smells`
already covers. The two features should stay visibly distinct in the UI
(§3) precisely because they answer different questions ("is this code
readable/safe" vs. "is this code doing more work than it needs to").

## 1. Proposed checks — 5, not padded to a round number

Every candidate from the original brief was evaluated against one bar:
**can this be detected with a genuinely low false-positive rate using
tree-sitter AST facts alone, without semantic/dataflow analysis this
codebase doesn't have?** One example from the brief was dropped because it
failed that bar (see §1.6) — reported honestly rather than force-fit.

### 1.1 Loop-invariant recomputation in a loop condition

**Pattern**: `strlen(x)` (or a `sizeof(x)/sizeof(x[0])`-shaped array-length
expression) appearing directly in a `for`/`while` loop's **condition**
clause, where `x` is never reassigned anywhere in the loop body.

**Why reliable**: this is a narrow, syntactically explicit shape — `for
(i = 0; i < strlen(s); i++)` is one of the most well-known, specific C
anti-patterns that exists (it silently turns an O(n) scan into O(n²),
since `strlen` re-scans from the start every single iteration). Detection
doesn't require knowing what `strlen` "means" in general — only: is this
call inside a loop condition, and is its argument variable untouched in
the loop body (checkable via a simple assignment/address-of scan over the
body, the same style of "nearby lookahead" scan `auto_patch.py` already
uses for its NULL-check/free-reset heuristics). Real risk of false
negatives (missing cases where the variable **is** technically mutated but
provably not in a way that changes the string length) is acceptable; false
**positives** are what this bar is about, and this pattern has very few.

### 1.2 String growth via repeated `strcat`/`sprintf`-append inside a loop

**Pattern**: `strcat()`, `strncat()`, or `sprintf()`/`snprintf()`
appending into the *same* destination variable, called inside a loop body,
with no evidence of a tracked-offset/growable-buffer idiom (no separate
"current length" variable being threaded through).

**Why reliable**: like §1.1, this is a well-established, specific
anti-pattern — `strcat` must re-scan the destination for its NUL
terminator on every call, so calling it once per loop iteration to build
up a string is O(n²) total. Detecting "is this call textually inside a
loop body" is a direct AST containment check, no semantic analysis
required. False positives are low because there's essentially no
legitimate reason to call `strcat` repeatedly in a loop when the
alternative (track an offset, write directly) is standard practice.

### 1.3 Linear (non-geometric) `realloc()` growth inside a loop

**Pattern**: `realloc(ptr, <expr>)` inside a loop body where `<expr>`
grows by a small, textually-constant amount each iteration (`+1`, `+
sizeof(x)`, or using the loop counter/increment variable directly) rather
than a doubling/geometric pattern.

**Why reliable**: same AST-containment technique as §1.2, applied to
`realloc`'s size argument instead of a string-append call. Reallocating by
a constant increment on every iteration is a textbook O(n²) amortized-cost
mistake (each `realloc` may copy the whole buffer); doubling is the
standard fix and is easy to distinguish syntactically (an increment
expression vs. a multiplication/shift expression).

### 1.4 Heap allocation inside a loop body (review flag, not a definite bug)

**Pattern**: `malloc`/`calloc`/`realloc` call located inside a loop body.

**Why this one is framed differently**: unlike §1.1–1.3, "allocating
inside a loop" is not always wrong — sometimes each iteration genuinely
needs its own, separately-owned allocation. The AST fact itself (is this
call inside a loop body?) is 100% reliable to detect; what's *not*
reliable is judging intent. This check is proposed as a **review flag**
("N heap allocations inside this loop — confirm this is intentional, not
hoistable"), explicitly worded as a prompt to check rather than an
assertion of a bug — matching this codebase's existing tone for
lower-certainty findings (e.g. `patch_safety.py`'s honest "capacity not
known" disclosures).

### 1.5 Struct passed by value where a pointer would avoid a large copy

**Pattern**: a function parameter whose type is a `struct` (defined
elsewhere in the same file, not a pointer/array parameter) with more than
a threshold number of members (proposed: >4, matching the existing
`long_parameter_lists` threshold already used elsewhere in this file for
consistency).

**Why reliable, with an honest caveat**: "is this parameter a plain struct
type, not preceded by `*`" is syntactically unambiguous via tree-sitter.
What is *not* precise is the actual byte size — member count is a proxy,
not a real `sizeof()`. This must be labeled explicitly as an approximation
("struct with N members passed by value — likely copies more than
necessary") rather than implying a measured byte cost, consistent with how
this codebase already avoids overclaiming precision it doesn't have.

### 1.6 Dropped from the original brief: general O(n²)-or-worse nested loops

**Explicitly not included.** Flagging "any nested loop" is not viable at a
low false-positive rate — nested loops are extremely common and very
often necessary (2D array/matrix iteration is the obvious case). The
brief's own phrasing ("...with a single-pass alternative") requires
judging whether a *simpler* algorithm exists, which is a semantic
question this deterministic, AST-only approach cannot answer reliably. A
narrower version was considered (e.g. flagging nested loops that appear to
be doing an O(n²) pairwise-duplicate check where a hash set would do) but
was judged too speculative to commit to without a false-positive rate this
design can't actually verify in advance. Reporting this honestly rather
than shipping a noisy version of it.

## 2. Reuse of existing infrastructure — confirmed, two levels

**File-walking / batch-scan infrastructure**: a new `backend/
optimization_analyzer.py` plugs in exactly where `code_intelligence.py`
already does. It does **not** need a parallel pipeline — every scan entry
point (single-file, batch, GitHub) already funnels through the same
`ScanRecord` + `analysis_cache` machinery that `code_smells`,
`line_risk_scan`, and dangerous-API detection already use. The proposed
integration point is a new `analysis_cache.get_optimization_findings(record)`
function, following the exact same lazy, per-`ScanRecord.id`-cached
pattern `get_intel()`/`get_line_risks()` already use — computed on first
request (e.g. when a UI page asks for it), not eagerly at scan-creation
time, so **batch/GitHub scan speed is unaffected** unless a user actually
opens a page that requests these findings.

**Per-function walker (shared with Section A's redesign)**: `code_intelligence.parse()`
+ `find_functions()` already give per-function AST access today,
independent of whether `ml_bridge`'s own ML inference is file-level or
becomes per-function-level (see `docs/PER_FUNCTION_INFERENCE_DESIGN.md`).
§1.1–1.5's checks are all most naturally scoped "within one function's
body," so `optimization_analyzer.py` can use this today without waiting
for that redesign. If that redesign does ship, the specific "enumerate
functions, get each one's text/line-range" utility could be factored out
once and shared by both, rather than each maintaining its own tree-sitter
traversal — worth doing at that point, not a blocker now.

## 3. Proposed UI placement

**Recommended: a new, clearly-separated section on `Recommendations.tsx`**,
not a new dedicated page. Reasoning: that page is already this
platform's home for non-ML, rule-based guidance (`BEST_PRACTICES` panels,
`suggested_rewrite`) with an existing visual/conceptual separation from
the ML verdict shown on `Analysis.tsx`. Adding a new panel there —
explicitly headed "Performance & Efficiency Suggestions (heuristic-based,
not part of the vulnerability score)" — reuses an existing, already-honest
pattern instead of adding yet another page to an already-large sidebar
(49+ routes today).

**Alternative considered**: a new dedicated page (matching `AutoPatch.tsx`'s
pattern of "one page per remediation concern"). Not recommended as the
default — the content here is closer in shape to the existing
`BEST_PRACTICES` panels (a list of findings + why) than to AutoPatch's
per-instance diff cards — but worth raising as an option since it would
keep "security" and "performance" fully separated as distinct top-level
concepts, which has its own honesty value.

## 4. Expected overhead on batch/GitHub scans

Low, and not on the critical path. Since this is deterministic (no
CodeBERT, no model inference) and reuses the same parsed AST
`code_intelligence.py` already produces, its cost is comparable to the
existing `code_smells` computation — already proven fast and cacheable
(`analysis_cache.py`'s own measurement: `project_summary` dropped from
2.2–3.0s to 0.013s warm after caching this class of computation). Because
integration is lazy (§2), **scan creation time — the part that matters for
the 120s→10min timeout work in Section A — is unaffected**; the cost is
only paid when a user opens a page requesting these findings, once per
scan, cached thereafter.

One open implementation question for Phase 2, not resolved here: whether
`optimization_analyzer.py` re-parses the file independently (cleaner
module boundary, matches "same architectural pattern as the existing
dangerous-API detector") or is folded into `code_intelligence.analyze()`
directly (avoids a second tree-sitter parse pass, more efficient but less
modular). Worth deciding at implementation time, not a blocker to this
design.

## 5. Docs / honesty requirements for Phase 2

- API response fields explicitly labeled `"heuristic-based": true` (or
  equivalent), never merged into `vuln_probability`/`risk_level`.
- A short doc (or a section in an existing one, e.g. `docs/CI_CD.md`-style
  disclosure) stating plainly: rule-based, not ML-derived, separate from
  the vulnerability classifier, and — per §1.6 — explicitly listing what
  was considered and excluded for reliability reasons, not just what's
  included.
- Kept fully out of `paper/research_paper.md`'s ML/fusion research framing
  — this is a product feature, not part of the ablation/evaluation story.

## 6. Open questions for sign-off

1. Confirm the 5 checks in §1.1–1.5 (and the explicit exclusion in §1.6).
2. Confirm UI placement: new Recommendations.tsx section (recommended) vs.
   a new dedicated page (§3).
3. Confirm the `analysis_cache`-based lazy integration point (§2) rather
   than eager computation at scan time.

## 7. Implementation notes (Phase 2)

Built exactly as designed, no scope changes:

- **`backend/optimization_analyzer.py`** — the 5 checks from §1.1–1.5 only.
  Re-parses independently via `code_intelligence.parse()`/`find_functions()`
  (resolving the open question in the old §4 in favor of the cleaner module
  boundary, matching the dangerous-API detector's own architectural class).
  Every response includes `"heuristic_based": true`; nothing in this module
  computes or references `vuln_probability`/`risk_level`/the trained
  classifier. §1.6's exclusion (general O(n²) nested-loop detection) was
  **not** implemented, exactly as designed — not a gap, a deliberate
  reliability call already made in §1.6.
- **Wiring**: `analysis_cache.get_optimization_findings(record)` — same
  lazy, per-`ScanRecord.id`-cached pattern as `get_intel()`/
  `get_line_risks()`. New endpoint `GET /api/scan/{scan_id}/optimization`
  in `routers/intelligence.py`. Works unmodified across every existing scan
  entry point (single-file, batch/ZIP, GitHub) because all of them already
  produce the same `ScanRecord` rows this endpoint reads by id — no new
  scan pipeline needed, confirming §2's "reuse, don't duplicate" premise.
- **UI**: a new "Performance & Efficiency Suggestions" panel on
  `Recommendations.tsx` (§3's recommended placement, not a new page),
  explicitly subtitled "heuristic-based, not part of the vulnerability
  score" and visually separate from the security best-practices panels
  above it.
- **Tests**: `backend/tests/test_optimization_analyzer.py` — one
  known-inefficient fixture tripping all 5 checks (6 total findings, since
  a `realloc()` inside a loop is correctly counted by both §1.3 and §1.4 —
  they answer different questions, not a duplicate), one known-clean
  fixture (idiomatically correct equivalents: hoisted `strlen()`,
  offset-tracked `sprintf()`, a single exact-size `malloc()` outside any
  loop, a 2-member struct) tripping none. Plus a cache-identity test in
  `test_analysis_cache.py`.
- Not touched, as required: the ML/fusion pipeline, the 0.26 threshold, the
  trained models, or `paper/research_paper.md`.
