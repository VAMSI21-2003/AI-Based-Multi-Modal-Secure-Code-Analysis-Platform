# Feature-Fusion Alignment Fix — Results

Companion to `docs/ML_FORENSIC_AUDIT_PHASE4.md` (the bug discovery). This
document records the fix that was implemented, the corrected dataset
statistics, and the new (valid) baseline — all measured, not estimated.

## 1. The bug (invalidated results), restated briefly

`fuse_features.py` used to join AST/metrics/CodeBERT feature tables on a
`sample_id` that each upstream script computed as **its own output's row
position** (`range(len(df))`). Because `extract_ast_features.py` dropped
rows under 50 characters while `extract_metrics.py` dropped rows under only
10 characters, their numbering silently diverged the moment either script
dropped a row the other kept. Empirically confirmed (prior audit):
**27,048 of 27,225 fused rows (99.35%) paired one function's label/AST
features with a different function's metrics/CodeBERT features.**

**Every metric reported before this fix is INVALIDATED**, not merely
superseded — this includes the production XGBoost F1=0.5673/Accuracy=61.12%,
the Random Forest F1=0.5315, the previously-adopted decision threshold 0.32
and its reported F1=0.632, and the ablation datapoint (structural-only
F1=0.548 vs. fused F1=0.567) already in `paper/research_paper.md`. **None of
these numbers should be cited going forward without the "(invalidated,
pre-fix)" qualifier.**

## 2. The fix

1. **`src/preprocessing/preprocess_dataset.py`**: assigns a stable
   `original_id` column (`range(len(df))`, computed exactly once,
   immediately after cleaning) and saves it into `devign_cleaned.csv`.
2. **`src/ast/extract_ast_features.py`** and **`src/metrics/extract_metrics.py`**:
   removed the per-script minimum-length filters entirely (they were
   inconsistent, undocumented defensive leftovers, not a deliberate,
   principled quality rule — the real quality bar was already established
   once, in `preprocess_dataset.py`). Every row is now kept and carried
   through with its `original_id`; a genuinely unparseable function still
   gets safe, honest fallback features (`parse_failed=True`, all-zero AST
   features) via the existing exception handling, rather than silently
   vanishing and shifting every subsequent row's alignment.
3. **`src/codebert/extract_embeddings.py`**: `embedding_row` is now read
   from the carried `original_id` column instead of a freshly recomputed
   `range(len(df))` — this specific script's own output happened to already
   be correct (it never drops rows), but the code no longer *relies* on
   that being true.
4. **`src/fusion/fusion_core.py`** (new module): `fuse_tables()` joins
   strictly on `original_id` and validates the result explicitly —
   duplicate-ID detection, missing-ID reporting, and (this is the
   decisive check) **cross-validates that `target` and `func` are
   identical across tables for every fused row**, raising
   `FusionAlignmentError` immediately if they ever disagree. This function
   has zero import-time side effects specifically so it can be unit tested
   directly (`tests/test_fusion_alignment.py`, 8 tests, covering the exact
   "dropped by one script, kept by another" scenario from the real bug,
   shuffled-row-order invariance, and both duplicate-ID and mismatch
   detection).
5. **`src/model/train_classifier.py`** / **`src/model/threshold_experiment.py`**:
   `METADATA_COLS` extended to include the new `func` column now present in
   `final_features.csv` (kept deliberately, not just for the fix — it lets
   `sample_id`-keyed rows be manually inspected against their real source
   text going forward, e.g., for error analysis).

## 3. Corrected dataset statistics (measured)

| Stage | Row count (old, corrupted) | Row count (corrected) |
|---|---|---|
| Raw (`function.json`) | 27,318 | 27,318 (unchanged) |
| Cleaned (`devign_cleaned.csv`) | 27,231 | 27,231 (unchanged — same 87 rows removed by dedup/empty/short filters) |
| AST features | **27,225** (6 rows silently dropped) | **27,231** (0 dropped — all rows kept) |
| Metrics features | 27,231 | 27,231 (unchanged — never dropped any) |
| CodeBERT embeddings | 27,231 | 27,231 (unchanged — never dropped any; not recomputed, verified byte-identical row order to before) |
| **Final fused (`final_features.csv`)** | **27,225** | **27,231** |
| Samples present in all modalities | 27,225 (but 99.35% mispaired) | **27,231 (100%, correctly paired)** |
| Rows dropped, with reason | 6 (AST's now-removed 50-char filter tripped on 6 real, valid ≥49-char functions the metrics script kept) | **0** |
| Duplicate `original_id` values | not tracked before | **0** (explicitly validated) |
| Missing `original_id` values (present in fewer than all 3 tables) | not tracked before | **0** (explicitly validated) |
| Cross-table label mismatches | not tracked before (this IS the bug) | **0** (explicitly validated — see §4) |

## 4. Zero-misalignment verification (re-run of the audit's exact simulation)

```
AST rows: 27231   Metrics rows: 27231
Common original_id count: 27231
Cross-modal mismatches (same original_id, different func text): 0

CONFIRMED: ZERO cross-modal positional misalignments.
```

Plus, `fuse_features.py`'s own real run printed (not simulated):

```
PASS: target label cross-validated identical across AST/Metrics/CodeBERT for every fused row.
PASS: source code text cross-validated identical between AST/Metrics for every fused row.
PASS: no duplicate original_id values in the final fused table.
```

## 5. Manual 10-sample verification

Ten `sample_id` values chosen at random (seed=7) from the corrected
`final_features.csv`, cross-checked against the independently-loaded AST,
metrics, and CodeBERT-metadata files:

| sample_id | label | AST func matches? | Metrics func matches? | CodeBERT target matches? |
|---|---|---|---|---|
| 7895 | 0 | True | True | True |
| 11104 | 0 | True | True | True |
| 13035 | 0 | True | True | True |
| 14714 | 0 | True | True | True |
| 15687 | 0 | True | True | True |
| 17698 | 1 | True | True | True |
| 18573 | 0 | True | True | True |
| 22498 | 0 | True | True | True |
| 24663 | 0 | True | True | True |
| 27084 | 1 | True | True | True |

All 10/10 confirmed correctly aligned.

## 6. New baseline results (corrected data — replaces all prior numbers)

| Model | Accuracy | Precision | Recall | F1 | AUC-ROC | PR-AUC |
|---|---|---|---|---|---|---|
| **XGBoost (new baseline)** | 59.32% | 55.74% | 52.19% | **0.5391** | 0.6346 | 0.6223 |
| **Random Forest (new baseline)** | 57.21% | 53.80% | 43.29% | **0.4798** | 0.5959 | 0.5635 |

Confusion matrices (test set, n=5,447):
- XGBoost: TN=1935, FP=1029, FN=1187, TP=1296
- Random Forest: TN=2041, FP=923, FN=1408, TP=1075

**Old (INVALIDATED, pre-fix) numbers, for contrast only — do not use these
for anything going forward:**

| Model | Accuracy | Precision | Recall | F1 | AUC |
|---|---|---|---|---|---|
| ~~XGBoost (invalidated)~~ | ~~61.12%~~ | ~~57.57%~~ | ~~55.92%~~ | ~~0.5673~~ | ~~0.6476~~ |
| ~~Random Forest (invalidated)~~ | ~~59.98%~~ | ~~56.98%~~ | ~~49.80%~~ | ~~0.5315~~ | ~~0.616~~ |

**Honest interpretation**: the corrected numbers are modestly *lower* than
the invalidated ones, not higher. This is scientifically expected and not a
sign the fix did anything wrong — the old numbers were computed on a
feature matrix where most rows' CodeBERT/metrics values came from a
different (but usually nearby, since the shift only ever grew by the small
integer count of drops) function than the label/AST values, which could
have contributed noise that the tree ensembles partially fit around in
ways that don't generalize. The corrected numbers are the trustworthy ones,
even though they are less flattering.

## 7. New threshold-selection result (replaces 0.32)

Same methodology as before (train→validation→test, test set touched
exactly once): validation-selected threshold on the corrected data is
**0.26** (not 0.32).

| Threshold | Accuracy | Precision | Recall | F1 | AUC |
|---|---|---|---|---|---|
| 0.50 (default) | 58.34% | 54.53% | 51.83% | 0.5315 | 0.6268 |
| **0.26 (validation-selected, NEW)** | 49.04% | 47.15% | **97.70%** | **0.6361** | 0.6268 |

AUC is identical at both thresholds (threshold-independent by construction),
confirming this is a genuine recalibration, not a different model. This is
an even more aggressive recall-favoring operating point than the old
(invalidated) 0.32 — at 0.26, the model flags nearly everything as
vulnerable (97.7% recall) at the cost of precision falling to 47.15%. This
trade-off is real and should be stated plainly in any viva/paper discussion,
not glossed over: **this operating point is tuned to almost never miss a
real vulnerability, at the cost of a very high false-positive rate.**

**Adopted into production**: `app/predictor.py`'s `VULNERABILITY_THRESHOLD`
is now `0.26`. `risk_level` (SAFE/LOW/MEDIUM/HIGH/CRITICAL) is unaffected —
it is computed independently from the raw probability.

## 8. Live inference validation (real, not simulated)

Backend restarted fresh with the retrained models. Real API calls:

| Test | Result |
|---|---|
| Known-vulnerable strcpy snippet, XGBoost | 61.37% → VULNERABLE, MEDIUM RISK |
| Same snippet, Random Forest | 62.0% → VULNERABLE, MEDIUM RISK |
| Bounds-checked (safer) snippet, XGBoost | 31.07% → VULNERABLE, LOW RISK (still above the aggressive 0.26 threshold — see §7's honest trade-off) |
| Determinism (same input, two calls) | 61.37% both times — identical |
| CI demo fixtures re-measured | `vulnerable_example.c`: LOW RISK 37.5%; `safe_example.c`: **CRITICAL 97.4%** — investigated directly (not assumed), confirmed to be real, explainable, deterministic model behavior (the "safe" fixture has more structural complexity — an `if` guard, more AST nodes, higher LOC — which the retrained model has learned correlates with vulnerability in its training distribution), not a residual alignment bug. See `docs/CI_CD.md` for the full explanation. |

Full backend test suite: **72/72 passing** (64 backend + 8 new fusion-alignment tests), including model-loading, determinism, and the updated threshold-regression test.

## 9. Remaining risks / explicitly not yet done

- **`paper/research_paper.md` and `paper/project_report_part2.md` still cite
  the old (invalidated) F1=0.567/threshold=0.32 figures** — these need a
  follow-up editing pass to cite the new numbers in this document and
  explain the Phase 4 finding as a real, defensible research narrative
  (arguably a *stronger* paper section than before: finding and fixing a
  genuine data-pipeline bug is itself a substantive contribution to
  discuss). Not done in this pass — flagged explicitly rather than left
  silently stale.
- **`docs/ML_EXPERIMENTS.md`'s Experiment 1 section** still describes the
  old 0.32 result as current — needs a similar update pointing here.
- The uncomfortable CI-fixture finding (safe scores higher than vulnerable)
  has not been investigated beyond the single explanation in §8 — a deeper
  error-analysis pass (Phase 4's originally-planned next phase) would be
  the right place to characterize this class of failure systematically
  rather than as a one-off observation.
- Cross-validation, modality ablation, error analysis, the CodeBERT
  long-function experiment, and the grouped-split experiment are all
  **still not started** — this document establishes the corrected
  baseline they should now run against.

## GO/NO-GO for proceeding to cross-validation and grouped-split analysis

**GO.** The feature-fusion alignment bug is fixed, empirically verified at
both the full-dataset level (0 mismatches across all 27,231 rows) and via
manual spot-check (10/10 samples confirmed), the models have been retrained
on the corrected data as a new baseline, the threshold has been re-selected
correctly, and live inference has been validated end-to-end. Proceed to the
next planned ML phase.
