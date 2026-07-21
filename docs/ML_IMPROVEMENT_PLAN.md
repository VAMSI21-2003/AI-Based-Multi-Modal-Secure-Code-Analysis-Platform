# ML Improvement Plan

Planning document only — no experiments have been run yet under this plan
(the threshold experiment in `docs/ML_EXPERIMENTS.md` was completed in a
prior session and is the one exception, already applied to production).
Everything below is what will be executed next, in order, once this plan is
approved.

## Experiment infrastructure (shared across all experiments below)

All experiments reuse the exact methodology validated for the threshold
experiment:
1. Reproduce the *exact* production split (`train_test_split(test_size=0.2,
   random_state=42, stratify=y)`) — this is the untouched final test set,
   touched exactly once, at the end, per experiment track.
2. Carve a validation set out of the training portion only (another
   stratified 80/20 split) for any model-selection or hyperparameter
   decision.
3. Save every experimental artifact under `results/experiments/`, never
   overwriting `models/xgboost.json` or `models/random_forest.joblib`.
4. Report Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC, confusion matrix
   for every configuration — no cherry-picking a single favorable number.

## Phase 1 (continued): forensic items not yet closed

| Item | Status | Next action |
|---|---|---|
| Grouped/project-aware split | **Not started** | Split `final_features.csv` by `project` (only 2 values: qemu/FFmpeg — too coarse for a meaningful grouped split) — the real grouping key needs to be `commit_id` if it has enough distinct values; measure how many distinct commits exist and whether a `GroupShuffleSplit` on commit_id is even meaningfully different from the current split before claiming an improvement either way. |
| 5-fold cross-validation | **Not started** | `StratifiedKFold(n_splits=5)` on the training portion only, report mean±std for F1/Precision/Recall/AUC. Compute cost: ~5x current single-split train time (~1 minute for XGBoost) — cheap, no reason to skip. |
| Feature redundancy check | **Not started** | Correlation matrix on the 11 AST + 13 metric features (already small enough to inspect directly); CodeBERT's 768 dims are the ones ablation (Phase 2) actually tests for redundancy at the branch level, not per-dimension. |

## Phase 2: Modality ablation — experiment design

Using the **existing trained-model hyperparameters** (XGBoost: 100 trees,
depth 6, lr 0.1) retrained on masked feature subsets of the identical
train/val/test split:

| Config | Feature columns kept | Dim |
|---|---|---|
| A. CodeBERT only | `embed_000`..`embed_767` | 768 |
| B. AST only | `n_*`, `max_depth` | 11 |
| C. Metrics only | `loc`, `function_count`, ... | 13 |
| D. AST + Metrics | B + C | 24 |
| E. CodeBERT + Metrics | A + C | 781 |
| F. CodeBERT + AST | A + B | 779 |
| G. Full fusion (current production config) | A + B + C | 792 |

**Methodology note, important**: this reuses `analyze_results.py`'s existing
ablation-masking approach already used for the paper's single reported
ablation point (structural-only 0.548 vs. fused 0.567) — masking columns to
zero on the **same trained full-fusion model** measures how much each
block's *information* the trained model actually relies on, which is subtly
different from training 7 *independently* fresh models on each column
subset. Both are legitimate experiments answering slightly different
questions:
- **Masking** (cheap, reuses the existing model): "how much does the
  production model's decision rely on each block?"
- **Independent retraining per subset** (the literal A–G ask): "what is the
  best achievable performance using only that modality?"

**This plan will run both**, since they answer different, both-useful
questions, and label results clearly as to which methodology produced them
— never conflate the two numbers.

**Expected outcome to watch for**: given the already-measured CodeBERT
anisotropy (mean pairwise cosine similarity 0.9833) and truncation (45.5%),
it's plausible that AST+Metrics alone captures most of the fused model's
performance, with CodeBERT contributing a real-but-modest lift (consistent
with the one existing ablation point). This will be reported honestly
whichever way the evidence points — **the plan explicitly commits, in
advance, to not treating a weak CodeBERT-alone result as grounds to remove
it**, since the existing masking ablation already shows it contributes
positively in combination, and per-modality performance in isolation isn't
the same question as marginal contribution to the fused model.

## Phase 3: CodeBERT long-function experiment — design

| Config | Description |
|---|---|
| Baseline | Current: first 512 tokens, single `[CLS]` embedding (production) |
| A: sliding window + mean pool | Split into overlapping 512-token windows (stride 256), embed each, mean-pool across windows |
| B: sliding window + max pool | Same windows, element-wise max-pool instead of mean |
| C: attention-weighted pool | Only if A/B show a meaningful signal — a lightweight learned attention over window embeddings adds real complexity/compute cost that isn't justified to build speculatively |

**Critical evaluation split, per your explicit instruction**: report
metrics separately for **functions ≤512 tokens** and **functions >512
tokens** in addition to the overall number — the whole point of this
experiment is whether long functions specifically improve, and an
overall-average number could hide a wash-on-short-functions-but-better-
on-long-functions result (or vice versa) that matters more than the blended
average.

**Compute cost to measure and report, not assume**: embedding time scales
roughly linearly with window count for the ~45.5% of functions needing >1
window; this needs to be measured on real hardware (this project's CPU-only
setup) before any adoption decision, not estimated.

**Decision rule, stated in advance**: adopt only if validation-set F1 (or
PR-AUC, given class balance is only mild) improves by a margin larger than
what would be explained by re-running the baseline with a different random
seed — i.e., don't adopt a difference smaller than normal run-to-run noise.
Single-run noise magnitude will be estimated by re-running the baseline
config 3x with different seeds before comparing against the windowed
approaches.

## Phase 4: Error analysis — design

Pull actual false positive / false negative examples from the untouched
test set's predictions (already computable without touching the test set
"for tuning" — reading predictions for analysis after final evaluation is
not the same as using them to select a model/threshold). Categorize each by:
- token count (truncated vs. not, using the real per-sample token count,
  not the aggregate 45.5% statistic)
- `n_error_nodes` from AST (parse quality proxy)
- confidence (distance of `vuln_probability` from the 0.32 threshold —
  low-confidence errors near the boundary vs. high-confidence wrong
  predictions, which are more concerning)
- presence of a dangerous-API deterministic-evidence hit vs. ML-only
  disagreement (cases where the evidence layer and the ML model disagree
  are a distinct, interesting bucket)

Output: `docs/ML_ERROR_ANALYSIS.md` with real examples (code snippets),
capped/redacted only if something sensitive appears (unlikely — Devign
source is public open-source C).

## Execution order recommendation

1. Cross-validation (cheapest, strengthens every other number's credibility)
2. Modality ablation (both masking and independent-retrain variants)
3. Error analysis (informs whether the long-function experiment is even the
   right next lever, or whether label noise / a different issue dominates)
4. Long-function CodeBERT experiment (most expensive, most speculative payoff)
5. Grouped-split comparison (closes the leakage question properly; lowest
   urgency given the already-established small bound)

This order front-loads the cheapest, highest-confidence experiments and
lets error analysis (step 3) inform whether step 4's significant effort is
actually likely to pay off before committing to it.
