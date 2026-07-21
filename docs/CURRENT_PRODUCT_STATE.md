# Current Product State (Read-Only Audit)

Consolidates and re-verifies findings from this session's prior audits
(`FINAL_PRODUCT_AUDIT.md`, `ML_PIPELINE.md`, `ML_EXPERIMENTS.md`) plus fresh
investigation of the remediation engines specifically for this pass. No code
was changed to produce this document.

## 1. ML pipeline (real, measured)

`dataset/processed/final_features.csv` (27,225 samples, qemu 17,499 / FFmpeg
9,726) → `src/model/train_classifier.py` (`train_test_split(test_size=0.2,
random_state=42, stratify=y)`) → XGBoost (100 trees, depth 6, lr 0.1,
`scale_pos_weight`) / Random Forest (100 trees, `class_weight="balanced"`) →
`models/xgboost.json` / `models/random_forest.joblib` /
`models/training_metadata.json`.

**Production metrics** (from the real artifact, threshold 0.5 — the
evaluation protocol reported in the paper):

| Model | Acc | Prec | Rec | F1 | AUC |
|---|---|---|---|---|---|
| XGBoost | 61.12% | 57.57% | 55.92% | 0.5673 | 0.6476 |
| Random Forest | 59.98% | 56.98% | 49.80% | 0.5315 | 0.616 |

**Live decision threshold is 0.32, not 0.5** — `app/predictor.py`'s
`VULNERABILITY_THRESHOLD = 0.32` constant, applied to `vuln_probability`
directly (not `model.predict()`'s implicit cutoff). This was selected via a
real train/val/test experiment (`docs/ML_EXPERIMENTS.md`), evaluated once on
the untouched test set: **F1 0.554→0.632, Recall 54.3%→90.4%, Precision
56.6%→48.6%, AUC unchanged at 0.638** (confirming the change is a genuine
recalibration, not a different model). A regression test
(`test_verdict_threshold_matches_the_validated_constant`) guards this.
**risk_level (SAFE/LOW/MEDIUM/HIGH/CRITICAL) is independent of this
threshold** — computed directly from `vuln_probability` via
`get_risk_level()`, unaffected by the verdict cutoff.

**Known, measured limitations, not yet acted on:**
- **CodeBERT truncation: 45.5%** of a 1,000-function sample exceed 512
  tokens (measured directly with the real tokenizer, not estimated) — vuln
  functions truncate slightly more (47.6%) than safe ones (43.6%). This
  figure corrected an earlier, wrong "12%" estimate that had been in the
  paper; both `paper/research_paper.md` and `paper/project_report_part2.md`
  have been corrected this session.
- **Near-duplicate leakage bounded, not eliminated**: whitespace-normalized
  hashing found 30 near-dup groups (0.11% of the cleaned dataset); worst-case
  cross-split contamination is bounded at ≤0.55% of the test set. Not
  large enough to explain F1=0.567 on its own. A grouped/project-aware split
  has **not** been run yet — this is unstarted work, not a completed
  experiment.
- **No cross-validation** — single fixed split only. Not yet run.
- **No modality ablation has been run** — the "multi-modal fusion helps"
  claim currently rests only on one ablation number already in the paper
  (structural-only F1 0.548 vs. fused F1 0.567) from prior work, not the
  full A–G ablation matrix this phase's brief asks for. **This is the
  single most important unproven claim in the project** given it directly
  underlies "multi-modal" in the project's own title.
- **No systematic error analysis has been performed** — false
  positive/negative examples have not been pulled from the test set and
  categorized. Unstarted.

## 2. Auto-Patch / remediation — TWO separate, overlapping engines exist

This is a real architectural finding from this pass, not previously
documented clearly:

**Engine 1: `backend/auto_patch.py`** (feeds `AutoPatch.tsx`, the dedicated
page) — per-file, generates "detected" cards (real regex match against the
actual scanned code, with a genuine before/after) for: `strcpy`→`strncpy`,
`gets`→`fgets`, `sprintf`→`snprintf`, `scanf("%s")` width-limit, free-without-
NULL-reset (double-free), integer-overflow-in-malloc guard, and malloc-
without-NULL-check. Falls back to 4 "reference" (canonical, not-detected)
cards for pointer misuse, buffer overflow via memcpy, NULL dereference, and
memory leak, when no live instance is safely auto-fixable.

**Engine 2: `backend/recommendations.py::suggest_secure_rewrite`** — a
*separate* regex rewrite list (`AUTO_FIXES`): `strcpy`, `strcat`, `gets`,
`sprintf` (at least 4 confirmed, likely more below what was read this pass).
This is embedded directly in **every single-code scan's response**
(`routers/scan.py`'s `"suggested_rewrite"` field), not surfaced on a
dedicated page — a different code path than Engine 1, doing overlapping work
with slightly different transformation logic.

**Both engines share the same unverified assumption**: the `sprintf`/`strcpy`
fixes emit `sizeof(dest)`, which is only correct if `dest` is a stack array.
If the real destination is a pointer parameter (extremely common in real C
code — e.g. `void f(char *buf, ...)`), `sizeof(dest)` silently evaluates to
the pointer's size (4 or 8 bytes), not the buffer's real size — **the
"safer" rewrite can silently truncate data or, if the buffer is smaller than
the pointer size assumption breaks in the other direction, provide a false
sense of safety**. This has not been caught by any existing test because all
existing test snippets happen to use stack-array destinations.

**Missing entirely (confirmed again this pass): apply-patch, re-scan,
before/after risk comparison.** `AutoPatch.tsx` only calls `getPatches()` and
renders read-only diffs. No endpoint applies a patch to code and re-invokes
`ml_bridge.run_prediction`. This is the single largest missing *product*
capability audited so far.

## 3. Scan pipeline / ingestion (real, already hardened this session)

Folder upload (`webkitdirectory`+`webkitRelativePath`), ZIP upload
(in-memory, Zip-Slip guard + zip-bomb member/size caps added this session),
GitHub scanning (commit SHA/branch persistence, `files_detected/analyzed/
skipped/skip_reasons` now surfaced in both GitHub Mode and batch upload UI)
— all confirmed real end-to-end via live browser tests, not just code
reading, in the immediately preceding session turns.

## 4. Performance (real, measured, already fixed this session)

`project_summary`/`dependency_graph`/`knowledge_graph` were recomputing
`code_intelligence.analyze()` + `ml_bridge.line_risk_scan()` from scratch on
every request. Fixed via `backend/analysis_cache.py` (keyed by
`ScanRecord.id`, safe because those fields are write-once). Measured:
`project_summary` 2.2–3.0s → 0.013s warm; the cache is shared across all
three endpoints. **Not yet measured this session**: CodeBERT inference time
at scale (10/50/100/200 files), whether CodeBERT model loading/tokenizer
calls are ever redundantly repeated, whether GitHub scanning is parallel or
sequential per file (currently sequential, per `github_service.py`'s
`for full in matched_files:` loop — confirmed sequential, not yet measured
for parallelization opportunity).

## 5. Test coverage (real, current count: 37 backend / 9 frontend)

| File | Count | Covers |
|---|---|---|
| `test_feature_extraction.py` | 8 | AST/metric shape+correctness, validate_code, risk thresholds, malformed-source resilience |
| `test_ml_pipeline.py` | 8 | determinism, 792-dim fusion order, GitHub URL validation (incl. flag-injection), empty-code 400, threshold-constant regression |
| `test_github_batch_meta.py` | 5 | commit-SHA persistence across restart, 404 handling |
| `test_analysis_cache.py` | 3 | cache identity/independence |
| `test_batch_upload_security.py` | 11 | Zip Slip (7 unit + 1 integration), zip-bomb member cap, skip-reason reporting, corrupt-ZIP non-crash |
| `test_health.py` | 2 | health endpoint, router registration |

**Zero tests exist for**: Auto-Patch generation correctness, `recommendations.py`'s
`suggest_secure_rewrite`, the sprintf/strcpy `sizeof(dest)` risk identified
in §2, modality ablation, or any ML experiment beyond the threshold
regression.

## 6. Security (partially hardened this session, not fully audited)

Done: Zip Slip guard, zip-bomb caps, GitHub URL scheme/flag-injection
validation. **Not yet checked this session**: SSRF via GitHub URL (can a
URL resolve to `127.0.0.1`/`169.254.169.254`/internal ranges and still pass
`_validate_url`'s regex? The regex only checks URL *syntax*, not resolved IP
— this is a real, unverified gap), subprocess argument-injection beyond the
leading-dash check already tested, temp-directory cleanup guarantees under
exception paths, CORS configuration review, secrets-in-logs review.

## 7. Authentication

Confirmed (prior session pass): none anywhere in the FastAPI app. Not yet
decided whether this is an accepted scope limitation (single-user local
tool) or a gap to close — deferred to Phase 11 per your instructions.
