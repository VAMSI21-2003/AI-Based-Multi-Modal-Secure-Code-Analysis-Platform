# Remediation Engine Plan

Planning document — no code changed yet. Based on the two-engine finding in
`docs/CURRENT_PRODUCT_STATE.md` §2.

## 1. Consolidate before extending

Before adding the re-scan loop, the two overlapping engines
(`auto_patch.py` vs. `recommendations.py::suggest_secure_rewrite`) need a
decision, not a third parallel system:

- **Keep `auto_patch.py` as the primary, user-facing engine** (it already
  has per-pattern explanations, CWE tags, and a dedicated page) and extend
  *it* with the re-scan loop.
- **`suggest_secure_rewrite`'s embedded `"suggested_rewrite"` field on every
  single-scan response** should either be removed (if `Analysis.tsx`/
  `Scanner.tsx` don't meaningfully use it beyond what `AutoPatch.tsx` already
  shows better) or explicitly reconciled to share the *same* underlying
  pattern list as `auto_patch.py` so there is one source of truth for "what
  counts as a safe rewrite," not two lists that can silently drift apart.
  **This needs a quick check of where `suggested_rewrite` is actually
  rendered in the frontend before deciding** — not yet done as part of this
  planning pass.

## 2. Confidence levels per existing pattern (Phase 6 requirement)

Assessed against the actual regex/replacement logic in `auto_patch.py`:

| Pattern | Current behavior | Confidence | Why |
|---|---|---|---|
| `strcpy`→`strncpy`+NUL | Direct substitution on the matched call | **HIGH** | Semantically equivalent for the overwhelmingly common case; the one real risk (`sizeof(dest)` wrong if `dest` is a pointer parameter, not a stack array) applies here too — see §3 |
| `gets`→`fgets` | Direct substitution, adds `stdin` | **HIGH** | Universally correct transformation, no buffer-size ambiguity beyond the same `sizeof` risk |
| `sprintf`→`snprintf` | Direct substitution | **MEDIUM** | Same `sizeof(dest)` risk as strcpy, and `sprintf`'s destination is a pointer parameter *more often* than `strcpy`'s (format-string builders commonly take `char *buf` args) — real risk of silently wrong size |
| `scanf("%s")` fix | **Not a targeted substitution** — emits a generic `char buf[64]; scanf("%63s", buf);` canonical example, disconnected from the actual matched variable names | **LOW** | This is closer to a reference example mislabeled as a specific fix; should be relabeled honestly as "reference" (like the 4 already-honest reference cards) until it's rewritten to actually substitute the real variable name and a real, inferred size |
| free-without-reset → `var = NULL` | Purely additive line | **HIGH** | Cannot break a correct program; the only failure mode is a false positive (flagging a free() that's actually the function's last use of the pointer), which is safe to always apply |
| malloc-multiply overflow guard | Inserts a `return NULL;` guard before the allocation | **MEDIUM** | Correct in isolation, but assumes the enclosing function's return type is pointer-compatible with `NULL` — **not verified against the actual function signature**, and doesn't account for other resources already allocated earlier in the function that would leak on this early return |
| malloc-without-NULL-check | Inserts an `if (var == NULL) { ...; return NULL; }` block | **MEDIUM** | Same return-type-compatibility risk as above |

**Immediate, low-risk fix to apply first**: relabel the `scanf` card as
"reference" (not "detected"/auto-fixable) until its substitution is made
real — this is a one-line change to `_scan_line_patterns` (drop it from the
regex-substitution path, add an equivalent reference card) and directly
improves honesty without touching anything risky.

**Medium-term fix**: the two malloc-guard patterns need the enclosing
function's return type (available from `code_intelligence`'s AST function
data, which already extracts `return_type` per function — see
`code_intelligence.py:152 _return_type`) before inserting a `return NULL;`
guard. If the return type isn't pointer-compatible, either skip the
auto-insert and fall back to a reference-only card, or use a
context-appropriate sentinel (e.g. `return -1;` for `int`-returning
functions). This is a real, scoped fix, not a rewrite of the engine.

## 3. Re-scan loop — implementation design (Phase 5)

New endpoint: `POST /api/scan/{scan_id}/apply-patch`

Request: `{ "patch_id": "strcpy-1" }` (references a card ID from the same
`generate_patches()` output already served).

Flow:
1. Load the original `ScanRecord` by `scan_id`.
2. Re-run `auto_patch.generate_patches(record.code)` to get the current
   card list (never trust a stale card ID from an old page load — the code
   hasn't changed, so this is cheap and guarantees the patch still applies
   to the current content).
3. Apply the specific card's line-level substitution to a **new, separate
   code string** — never mutate `record.code` in place. The original scan
   row is immutable history; the patched version is a *new* scan.
4. Run the **exact same** `ml_bridge.run_prediction(patched_code, record.model_used)`
   used by every other scan in the system — no separate "verification"
   inference path.
5. Store the patched result as a new `ScanRecord` (source=`"patch"`,
   linked to the original via a new nullable `parent_scan_id` column —
   additive, no migration risk, same pattern as `is_pinned`/`tags`).
6. Response includes both records' `vuln_probability`/`risk_level`/`verdict`
   plus a computed `risk_delta` and one of exactly four labels:
   - `"Risk reduced"` (patched probability strictly lower)
   - `"Risk unchanged"` (within a small tolerance, e.g. ±2 percentage points)
   - `"Risk increased"` (patched probability strictly higher)
   - `"Re-scan inconclusive"` (only if inference itself failed, e.g. patched
     code fails `validate_code`)

**Never returned**: "Fixed successfully" or any wording implying certainty
beyond what the re-scan measured. Language will follow your exact
specification: "Patch proposed" → "Patch applied" → "Re-scan completed" →
one of the four labels above.

**Frontend**: `AutoPatch.tsx` gets an "Apply & Re-scan" button per detected
card (not reference cards — those have no live instance to apply). Shows a
before/after pair (reusing existing `Gauge`/`RiskBadge`/`VerdictPill`
components already used elsewhere, not new visual components) plus the
plain-language risk-delta label.

## 4. Testing plan for the re-scan loop

- Unit: apply the `strcpy` patch to `VULNERABLE_SNIPPET`, assert the patched
  code no longer contains `strcpy`, assert it still parses (AST feature
  extraction doesn't throw).
- Integration: full `POST /apply-patch` round trip on a known-vulnerable
  snippet, assert `risk_delta` is computed and one of the two ScanRecords
  has `source == "patch"` with `parent_scan_id` set correctly.
- **Negative test, important**: construct a patch that does NOT reduce risk
  (or use a snippet where the "fix" is superficial) and assert the endpoint
  honestly reports `"Risk unchanged"` or `"Risk increased"` — not just test
  the happy path where the patch obviously helps. This directly tests your
  Rule 15 ("if you discover a problem, measure it, fix it, re-measure it")
  applied to the feature itself.

## 5. What this plan deliberately does NOT do yet

- No LLM-based patch generation — everything above stays within the
  existing deterministic/regex engine, per your Phase 6 instruction that
  automatic application should only ever apply to HIGH-confidence,
  well-understood transformations.
- No compilation/build verification — per your Phase 8 acknowledgment that
  this may not be feasible for arbitrary C snippets without a full build
  environment; the re-scan step will be clearly labeled "vulnerability
  re-analysis," not "compilation verified," unless a build step is added
  later as a separate, explicitly-scoped feature.
