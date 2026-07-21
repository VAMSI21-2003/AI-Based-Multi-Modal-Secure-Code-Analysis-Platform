# ML Pipeline Forensic Audit (Phase 4) — READ-ONLY

No code, data, models, or configuration were modified to produce this
report. All findings are from direct inspection of `src/`, `app/`,
`backend/ml_bridge.py`, the actual dataset files, and fresh, real
computations run against the real data in this session (not estimated).

## 1. Executive Summary

**A critical, previously undiscovered data-integrity bug was found and
empirically confirmed**: `fuse_features.py` joins the AST, software-metrics,
and CodeBERT feature tables purely on an integer `sample_id` that each
upstream script assigns as **its own output's row position**, not a shared,
stable original-dataset index. Because `extract_ast_features.py` drops rows
under 50 characters while `extract_metrics.py` drops rows under only 10
characters, **6 real rows are dropped by the AST script but kept by the
metrics/CodeBERT scripts** — and once even one row is dropped, every
`sample_id` after it refers to a different original function in the AST
table than in the metrics/CodeBERT tables. This was verified empirically
against the real `dataset/processed/devign_cleaned.csv`: **27,048 of 27,225
final rows (99.35%) pair the label and AST features of one function with
the software-metrics and CodeBERT embedding of a different, nearby function.**

This means the production model (`models/xgboost.json`,
`models/random_forest.joblib`) was trained on a feature matrix where, for
essentially the entire dataset, the CodeBERT and metrics branches do not
describe the same code as the label and AST branches. **Every previously
reported classification metric (F1=0.567, the tuned-threshold F1=0.632, the
ablation's 0.548 structural-only figure) was computed on this same corrupted
matrix and cannot be trusted as measuring what it claims to measure.**

Separately, real group-leakage exposure was confirmed (12,290 distinct
commits, mean 2.2 functions/commit, one commit contributing 588 rows) — a
plain random split can and very likely does place same-commit functions on
both sides of the train/test boundary. Near-duplicate leakage remains
small (≤0.55% of test set, previously bounded). Threshold selection (0.32)
was methodologically sound (train→val→test, no test-set peeking) — but its
numeric result is only meaningful once evaluated on a correctly-fused dataset.

**GO/NO-GO: NO-GO.** Do not proceed to cross-validation, modality ablation,
error analysis, or the CodeBERT long-function experiment until the fusion
join is fixed and `final_features.csv` (and the model trained on it) is
regenerated. Running any of Phase 1's planned experiments on the current
artifact would produce numbers that look rigorous but measure a corrupted
dataset.

## 2. Complete ML Pipeline Trace

```
dataset/raw/ (Devign function.json / train+valid+test.jsonl)
  → src/preprocessing/preprocess_dataset.py   [Day 4]
      dropna → drop_duplicates(func) → drop empty → drop <50-char (PRE-whitespace-clean length)
      → whitespace-clean func text → save devign_cleaned.csv (27,231 rows)
  → src/ast/extract_ast_features.py            [Day 5]
      per-row: if len(func.strip()) < 50: SKIP (continue)  <-- drops 6 rows, see §8
      → devign_ast_features.csv (27,225 rows, in survivor order)
  → src/metrics/extract_metrics.py              [Day 6]
      per-row: if len(func.strip()) < 10: SKIP (continue)  <-- drops 0 rows in practice
      → metrics_features.csv (27,231 rows, faithful order)
  → src/codebert/extract_embeddings.py          [Day 7]
      no per-row length filter; only MAX_SAMPLES prefix truncation;
      embedding_row = true original devign_cleaned.csv row index;
      failed batches are ZERO-FILLED, never dropped
      → codebert_embeddings.csv (up to MAX_SAMPLES rows, faithful order)
  → src/fusion/fuse_features.py                 [Day 8]
      ast_df["sample_id"]      = range(len(ast_df))       <-- POSITION in AST's own survivor list
      metrics_df["sample_id"]  = range(len(metrics_df))   <-- POSITION in metrics' own (unfiltered) list
      codebert_df["sample_id"] = embedding_row (true original index)
      pd.merge(..., on="sample_id", how="inner") x2
      → final_features.csv (27,225 rows) -- SEE §8 FOR WHY THIS JOIN IS WRONG
  → src/model/train_classifier.py               [Day 9]
      train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
      RandomForestClassifier / XGBClassifier -- NO scaling, NO PCA, NO feature selection
      → models/xgboost.json, models/random_forest.joblib, models/training_metadata.json
  → backend/ml_bridge.py (inference)
      identical AST/metrics/CodeBERT extraction + concatenation order as training
      (see §15 — this part is CORRECT and consistent)
```

## 3. Leakage Audit

| Check | Status | Evidence |
|---|---|---|
| Scaling/normalization fitted on full dataset before split | **PASS** | No `StandardScaler`/`MinMaxScaler`/similar exists anywhere in `train_classifier.py` or `ml_bridge.py` — raw feature values are used directly. Nothing to leak. |
| PCA fitted on full dataset before split | **PASS** for training. `ml_bridge.py`'s `_pca_components()`/`pca_background()` are visualization-only (project a single embedding onto a precomputed 2D background for the UI scatter plot) — not part of the classifier's input pipeline. Not leakage into the model. |
| Feature selection using labels before split | **PASS** — no feature selection step exists at all; all 792 columns are always used. |
| Threshold selection using test set | **PASS** — see §11. |
| Labels leaking into features | **WARNING, indirect** — `target` is present as a column in `ast_df`/`ast_sel` alongside the AST features, carried through purely as metadata (correctly excluded from `X` via `METADATA_COLS` in `train_classifier.py`). Not used as a feature. However, because of the §8 misalignment, the `target` a row carries is tied to the AST features' (correct) function, but NOT to that row's metrics/CodeBERT features' (actual, different) function — this is not "label leakage" in the classic sense but is a related and arguably worse problem: the label is simply attached to the wrong multi-modal feature set for ~99% of rows. |
| Feature extraction introducing leakage | **FAIL** — see §8. Not "leakage" in the classic train/test sense, but a **cross-modal misalignment** that corrupts the meaning of the fused vector itself, independent of how the train/test split is later drawn. |

## 4. Duplicate/Near-Duplicate Audit

(Carried forward from prior verified work this session, re-stated here for completeness — not re-run, no new evidence needed.)

- Exact duplicates: 60 of 27,318 raw rows (0.22%), removed by `preprocess_dataset.py`.
- Near-duplicates (whitespace-normalized hash, this session's own measurement): 30 groups / 27,231 cleaned rows (≈0.11%); 26 of 30 groups have inconsistent labels (real Devign label noise).
- Exact cross-split contamination from these 30 groups: **Not verifiable from available evidence** at the row level (the §8 misalignment makes this doubly unverifiable now — even if we located the 30 groups' positions, the sample_id they'd carry post-fusion no longer reliably identifies "this same function" across modalities). Bound previously established (≤0.55% of test set, worst case) still holds as an upper bound on the *near-duplicate* leakage risk specifically, independent of §8.

## 5. Group/Project Leakage Audit

| Check | Status | Evidence |
|---|---|---|
| Project identity available | **PASS (but coarse)** | `project` column: only 2 values (`FFmpeg`, `qemu`) — too coarse to use as a meaningful group key (would just be a 2-fold split). |
| Commit identity available | **PASS** | `commit_id` column: **12,290 distinct values** across 27,231 rows (this session's fresh measurement), mean 2.22 rows/commit, real skew (top commit alone contributes 588 rows / 2.2% of the entire dataset). |
| Grouped/project-aware split feasible | **YES, confirmed feasible** | `sklearn.model_selection.GroupShuffleSplit` or `StratifiedGroupKFold` on `commit_id` is directly applicable — the data supports it structurally. Not implemented; this audit only confirms feasibility, per your instruction. |
| Is a random split currently allowing same-commit functions on both sides | **Almost certainly yes, not directly measured** | With 12,290 groups of mean size 2.22 and one group of 588, a plain `stratify=y`-only random split (no grouping) has no mechanism preventing same-commit rows from splitting across train/test — expected by construction, not measured row-by-row this pass (would require reproducing the exact split against `commit_id`, a cheap follow-up not done here to keep this phase strictly read-only/diagnostic as scoped). |

## 6. Preprocessing Order Audit

The **conceptual** order (clean → extract independently → fuse → split →
train) is standard and defensible in principle — feature extraction being
deterministic and label-independent per-sample, it doesn't matter whether it
happens before or after splitting, *provided the fusion join is correct*.
**The actual defect is not an ordering problem — it's a join-correctness
problem** (§8). Reordering steps would not fix this; only fixing the join
key would.

## 7. CodeBERT Audit

| Check | Status | Evidence |
|---|---|---|
| Embeddings generated independently of labels | **PASS** | `extract_batch_embeddings` takes only code text; label is carried separately as metadata. |
| Same procedure train vs. inference | **PASS** | `max_length=512, truncation=True, padding="max_length"` identical in `src/codebert/extract_embeddings.py` and `app/predictor.py` (grep-verified both sessions). |
| Max token length / truncation | **PASS (measured, not merely asserted)** | 45.5% of a 1,000-sample random draw exceed 512 tokens (this session's direct tokenizer measurement); vulnerable functions truncate slightly more (47.6%) than safe (43.6%). |
| 768-dim consistency | **PASS** | `EMBEDDING_DIM`/`EMBED_COLS` = 768 throughout; `embedding_dims` field in live inference confirms 768 at runtime. |
| Samples omitted/reordered/mismatched when joining | **FAIL — see §8.** CodeBERT's own extraction is faithful (zero-fills failures, never drops rows, uses true original index) — **CodeBERT is not the source of the bug**, but it is a victim of it: it gets joined against an AST table whose position-based `sample_id` has silently drifted. |

## 8. 792-Dimensional Feature Fusion Audit — CRITICAL FINDING

**Composition (as designed, and as-implemented dimensionally):** 11 AST +
13 metrics + 768 CodeBERT = 792. Column ordering
(`AST_FEATURE_COLS + METRICS_FEATURE_COLS + EMBED_COLS`) is consistent
between `fuse_features.py` and `app/utils.py::build_feature_vector` (test-
verified this session: `test_fusion_vector_has_exactly_792_dimensions_in_the_trained_order`
passes against live inference — **this consistency is real and unaffected
by the bug below**, since it's about column *order* within one already-built
row, not about *which two rows get concatenated*).

**The bug: row identity, not column shape.**

- `extract_ast_features.py` line ~463: `if len(code_text.strip()) < MIN_FUNC_LENGTH(=50): continue` — drops the row entirely from its output, shifting all subsequent output positions.
- `extract_metrics.py` line ~688: `if len(code_text.strip()) < 10: continue` — a **different, laxer threshold**.
- `fuse_features.py` lines 399, 431: `ast_df["sample_id"] = range(len(ast_df))` and `metrics_df["sample_id"] = range(len(metrics_df))` — **both assign sample_id as pure output-row-position**, not a stable reference back to `devign_cleaned.csv`. The script's own comment asserts "Row 0 in the AST file is the SAME function as Row 0 in the metrics file" — **true only if both scripts drop exactly the same rows, which they do not.**

**Empirical confirmation, run against the real dataset this session (not estimated):**

```
devign_cleaned.csv: 27,231 rows
Rows with 10 <= trimmed length < 50: exactly 6
  (original rows 177, 497, 9853, 10861, 13014, 20158 — all real, short,
   brace-only functions like "int kvm_has_pit_state2(void)\n{\n return 0;\n}")

AST survivor count: 27,225   Metrics survivor count: 27,231

Simulated position-based join (sample_id k -> AST's original row vs.
Metrics' original row), for k = 0..27,224:
  First divergence: sample_id = 177
    AST's sample_id=177  -> devign_cleaned.csv row 178 ("static void net_vhost_link_down...")
    Metrics' sample_id=177 -> devign_cleaned.csv row 177 ("int qemu_cpu_self(void *env)...")
  Total mismatched sample_id positions (of 27,225): 27,048  (99.35%)
```

Because `target` is carried through `ast_sel` (i.e., attached to the AST
table, not independently), **the label in `final_features.csv` is correctly
paired with the AST features** for every row — but for 99.35% of rows, that
same (label, AST-features) pair is fused with **metrics features and a
CodeBERT embedding belonging to a different, nearby function** (typically
1–6 positions away in the original dataset, since the shift only grows by
one at each of the 6 drop points).

**Status: FAIL.** This is not "leakage" in the train/test sense — it
corrupts the meaning of the fused feature vector itself, independent of how
any split is drawn. **Every model trained on `final_features.csv` in its
current form learned from a systematically mispaired multi-modal input for
essentially the entire dataset.**

**Scientific consequence:** the reported ablation finding ("CodeBERT adds a
modest lift, F1 0.548→0.567") and the threshold experiment's headline number
(F1 0.632 @ 0.32) were both computed on this same corrupted matrix. They are
**not necessarily wrong in direction** (the AST/label pairing is internally
consistent, and metrics/CodeBERT, while paired with the wrong specific
function, are still paired with *some* real code sample with a real label
of its own nearby in the dataset — so the fused vector isn't random noise,
but it is not what the pipeline documentation and the paper claim it is).
**No confidence interval can currently be placed on how much this affects
the reported numbers without regenerating the fusion correctly and
re-measuring.**

## 9. XGBoost Audit

| Item | Value | Status |
|---|---|---|
| n_estimators / max_depth / learning_rate | 100 / 6 / 0.1 | Fixed by convention, not tuned via CV — **WARNING** (not FAIL; a defensible research-scale default, but not validated as optimal) |
| Train/test split | `test_size=0.2, random_state=42, stratify=y` | **PASS** as a split *mechanism*; **input data is corrupted per §8** |
| Class weighting | `scale_pos_weight` computed per-training-set | **PASS**, appropriate technique for mild imbalance |
| Probability output | `predict_proba()[:, 1]` | **PASS**, standard, consistent with inference (`app/predictor.py`) |
| Saved model format | `models/xgboost.json` (native XGBoost JSON) | **PASS**, loads correctly (verified by existing `test_ml_pipeline.py` tests) |
| Inference compatibility | `XGBClassifier().load_model(path)` in both `train_classifier.py`'s save path and `app/predictor.py`'s load path | **PASS** |

## 10. Random Forest Audit

Same structure as §9: `n_estimators=100, max_features="sqrt", class_weight="balanced", random_state=42`. Saved via `joblib.dump`/`joblib.load`, format consistent, loads correctly. Same §8 corruption applies equally to this model (trained on the identical `final_features.csv`). **Status: same as XGBoost — mechanically sound, input data corrupted.**

## 11. Threshold 0.32 Audit

Traced `src/model/threshold_experiment.py` (written and run in a prior session, re-read in full this pass):

1. Reproduces the **exact** production `train_test_split` (same seed, same test_size) → the untouched test set.
2. Carves a validation set **out of the training portion only** (a second, different stratified split) — the test set is not touched again until step 4.
3. Retrains a fresh model (same hyperparameters) on the reduced training portion.
4. Sweeps thresholds 0.05–0.95 **on the validation set only**, selects 0.32 by validation F1.
5. Applies that single, pre-chosen threshold to the untouched test set **exactly once**.

**Status: PASS on methodology** — the test set was not used, directly or
indirectly, to select 0.32. This is genuinely train→validation→test, not
train→test. **However**, this experiment was run against `final_features.csv`
— the same §8-corrupted matrix. The *methodology* for selecting 0.32 is
sound; the *numeric result* (F1 0.554→0.632) inherits the same uncertainty
as every other metric until the fusion bug is fixed and the experiment is
re-run on a corrected matrix.

## 12. Class Imbalance Audit

Vulnerable 12,411 / Safe 14,820 in the cleaned dataset (45.6%/54.4%) — mild,
not severe. `stratify=y` used in every split (`train_classifier.py`,
`threshold_experiment.py`). `class_weight="balanced"` / `scale_pos_weight`
applied. **Status: PASS** — appropriate handling for this imbalance ratio;
F1/Precision/Recall (not raw accuracy alone) are the correctly-chosen
headline metrics given the mild imbalance.

## 13. Evaluation Metrics Audit

Metrics computed via standard `sklearn.metrics` calls
(`accuracy_score, precision_score, recall_score, f1_score, confusion_matrix`)
directly on `y_test`/`model.predict(X_test)` — **mechanically PASS**
(positive class correctly `1`=vulnerable, binary averaging is correct for a
binary problem, no macro/weighted ambiguity applies). **All of it operates
on the §8-corrupted `X_test`.** Status for the *numbers themselves*: **FAIL
(untrustworthy pending re-fusion)**, though the *calculation code* is correct.

## 14. Calibration Audit

XGBoost/Random Forest `predict_proba()` outputs are **not calibrated**
(no `CalibratedClassifierCV` or Platt scaling/isotonic regression anywhere
in the pipeline) — they are raw tree-ensemble class-probability estimates,
which are known in the literature to be reasonably rank-ordered but not
necessarily well-calibrated in an absolute sense (e.g., "70% probability"
does not necessarily mean "70% of such predictions are actually positive").
**The application's `risk_level`, `confidence`, and `vuln_probability` are
NOT scientifically interchangeable concepts**: `vuln_probability` is the raw
(uncalibrated) model output; `confidence` is a simple derived transform
(`vuln_probability` if predicted vulnerable, else `1-vuln_probability`);
`risk_level` is an independent bucketing of `vuln_probability` against fixed
thresholds; the `0.32` decision threshold is a separate, empirically-chosen
operating point on the same raw probability. All four are legitimate
concepts but must not be conflated as "the same number expressed
differently" — they are related but distinct transforms of one
uncalibrated raw score. **Status: WARNING** (not FAIL — this is a
disclosed, common, acceptable practice for tree ensembles, but should be
stated explicitly in the paper rather than implied to be calibrated
probabilities).

## 15. Train-vs-Inference Consistency Audit

| Check | Status | Evidence |
|---|---|---|
| Preprocessing identical | **PASS** | Same `extract_ast_features`/`extract_metric_features` functions imported directly by `ml_bridge.py` from `app/utils.py` — literally the same code, not a reimplementation. |
| AST features identical | **PASS** | Same function, same 11-column order (`AST_FEATURE_COLS`). |
| Metrics identical | **PASS** | Same function, same 13-column order (`METRICS_FEATURE_COLS`). |
| CodeBERT embeddings identical in shape/meaning | **PASS** | Same `max_length=512`/truncation settings; same model (`microsoft/codebert-base`), same `[CLS]` extraction. |
| Fusion ordering identical | **PASS** | `build_feature_vector()` in `app/utils.py` concatenates AST+metrics+embedding in the same order `fuse_features.py` used to build the training columns — verified by this session's own `test_fusion_vector_has_exactly_792_dimensions_in_the_trained_order` test, which passes. |
| Scaling/transformation identical | **PASS (both: none)** — no scaling anywhere, so nothing to mismatch. |
| Model input dimensions match | **PASS** | 792 in both. |
| Threshold behavior identical | **PASS** | `VULNERABILITY_THRESHOLD = 0.32` applied consistently in `app/predictor.py`'s single inference path used by every scan type (verified this session). |

**This section is the one clean bill of health in this audit**: whatever
happened at training time in `fuse_features.py` (§8), **live inference
itself does not have the row-alignment bug**, because at inference time
there is only ever one function being scanned — its AST, metrics, and
CodeBERT features are computed from the same, single, actual input code and
concatenated directly, with no cross-file positional join involved at all.
**The bug is confined to the offline training-data construction pipeline,
not the production inference path.**

## 16. Reproducibility Audit

| Item | Status | Evidence |
|---|---|---|
| Random seeds | **PASS** | `random_state=42` fixed and consistent across `train_classifier.py` and `threshold_experiment.py`. |
| Dataset version | **WARNING** | No hash/version pin on `dataset/raw/` — Devign is a static public dataset, but no checksum is recorded in this repo to prove the exact raw file used. |
| Preprocessing configuration | **PASS** | Fixed constants (`MIN_FUNC_LENGTH`, thresholds) hardcoded in each script, not parameterized — reproducible, if inconsistent across scripts (§8). |
| Model configuration | **PASS** | Hyperparameters hardcoded and documented in `training_metadata.json`. |
| Split configuration | **PASS** mechanically, **input corrupted** per §8. |
| Dependency versions | **UNKNOWN** — Not verifiable from available evidence without inspecting `requirements.txt` pins against what's actually installed; not checked this pass (out of explicit scope items but flagged for completeness). |

## 17. Current Results Validity

- **Trustworthy, unaffected by §8**: the 45.5% CodeBERT truncation measurement and the embedding anisotropy (0.9833) measurement — both computed directly against raw code text / a fresh tokenizer/model run this session, not through the corrupted fusion join. The near-duplicate/label-noise finding (30 groups, 26 inconsistent) — computed directly on `devign_cleaned.csv`. The train/inference consistency audit (§15). The threshold-selection *methodology* (§11) as a procedure.
- **Potentially biased / must be regenerated**: every classification metric computed on `final_features.csv` or any model trained on it — production XGBoost/RF F1/Precision/Recall/AUC, the threshold experiment's *numeric* result (0.554→0.632), the existing modality-ablation data point (structural-only F1 0.548 vs. fused 0.567).
- **Cannot currently be reproduced as claimed**: the implicit claim that "AST, metrics, and CodeBERT features describe the same function" for the training set — empirically false for 99.35% of rows.

## 18. Critical Issues Ranked by Severity

1. **[CRITICAL / FAIL] Feature-fusion row misalignment (§8).** Affects 99.35% of the training/test data. Invalidates every downstream reported metric until fixed. Root cause: inconsistent per-script length filters (50 vs. 10 chars) combined with position-only join keys.
2. **[HIGH / WARNING] Group/commit leakage exposure (§5).** Not yet measured directly, but structurally likely given 12,290 commits with real multi-row groups and no grouping applied in the current split.
3. **[MEDIUM / WARNING] Uncalibrated probabilities conflated with several related-but-distinct concepts (§14).** Not incorrect, but under-disclosed; a viva/paper risk if not stated explicitly.
4. **[LOW / WARNING] Near-duplicate leakage (§4).** Small, bounded (≤0.55% of test set), already documented.
5. **[LOW / WARNING] No dataset checksum/version pin (§16).**

## 19. Required Fixes Before Experiments

1. **Fix `fuse_features.py`'s join key.** Either (a) carry the true original `devign_cleaned.csv` row index through every extraction script (AST and metrics scripts would need a real "original_row" column, analogous to CodeBERT's `embedding_row`, instead of `range(len(df))`), or (b) join on the `func` text itself (exact string match) instead of a positional integer — slower but immune to any future length-filter drift between scripts. Recommend (a): cheapest, and forces the invariant to be explicit rather than assumed.
2. **Regenerate `devign_ast_features.csv` → `final_features.csv` end-to-end** with the fixed join, producing a corrected dataset. This requires re-running AST/metrics extraction (fast, CPU-only, minutes) — CodeBERT embeddings do NOT need to be recomputed (they were never wrong), only re-joined correctly.
3. **Retrain XGBoost and Random Forest on the corrected `final_features.csv`**, per Rule 12 ("do not retrain until experiments prove the new approach is better") — this is not an "improvement experiment," it is a correctness fix, and should be treated as establishing a new, valid baseline, not compared against the old (corrupted) one as if it were a competing hypothesis.
4. **Re-run the threshold experiment** on the corrected data before trusting 0.32 as the production threshold.
5. Only after 1–4: proceed to cross-validation, modality ablation, error analysis, and the CodeBERT long-function experiment — all currently planned experiments would otherwise run on the same corrupted matrix and produce equally untrustworthy results.

## 20. Recommended Experiment Order (once §19 is fixed)

Unchanged from `docs/ML_IMPROVEMENT_PLAN.md`'s original recommendation
(cross-validation → modality ablation → error analysis → long-function
experiment → grouped-split comparison), now correctly gated on the fusion
fix landing first. The grouped-split experiment (§5) should move up in
priority relative to the original plan, given the confirmed 12,290-commit
structure — it's now a cheap, well-motivated check to run early in the
corrected pipeline rather than a low-urgency nice-to-have.

---

## GO / NO-GO DECISION

**NO-GO.**

Do not proceed to cross-validation, modality ablation, error analysis, or
the CodeBERT long-function experiment. The feature-fusion join bug (§8)
must be fixed and the dataset/model regenerated first — this is a
correctness fix, not an experiment, and should be done before any of the
planned Phase 1 ML experiments, per your explicit instruction that this
phase remain read-only until you review these findings.
