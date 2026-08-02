# Cross-Validation Results

Companion to `docs/MODALITY_ABLATION_RESULTS.md`, which raised a question it
explicitly could not answer on a single 80/20 split: does full multi-modal
fusion (AST + Metrics + CodeBERT, 792-dim) actually beat CodeBERT alone
(768-dim) by more than ordinary sampling noise, or are they statistically
indistinguishable? On that single split, full fusion (F1 0.5391) scored
*below* CodeBERT-alone (F1 0.5418) — within about 1 point, explicitly flagged
there as needing cross-validation to resolve, not decided.

Produced by `src/model/cross_validation.py` — a new, standalone script that
only reads the already-fused, already-alignment-fixed
`dataset/processed/final_features.csv` and column-slices it, exactly like
`modality_ablation.py`. **It does not call, import, or modify
`extract_ast_features.py`, `extract_metrics.py`, `fuse_features.py`,
`fusion_core.py`, or the alignment logic in any way.** Nothing in `models/`,
`app/predictor.py`'s `VULNERABILITY_THRESHOLD` (0.26), or the live app was
touched.

Preceded by `src/model/verify_commit_grouping.py` (Phase 0 of this session),
which confirmed the commit-count/skew numbers this and the companion grouped-
split experiment depend on are still accurate on the real, current data —
see `docs/GROUPED_SPLIT_RESULTS.md` for that verification.

## 1. Methodology

- `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)` computed
  **once** on row indices + `target`, and reused for every modality subset
  below — every subset is evaluated on the identical 5 fold partitions, so
  differences between subsets reflect the features, not different folds.
  Verified reproducible: re-running `StratifiedKFold` with identical
  arguments produced the exact same fold assignments (asserted in the
  script, not assumed).
- Same XGBoost hyperparameters as production: `n_estimators=100,
  max_depth=6, learning_rate=0.1, random_state=42`. `scale_pos_weight` is
  computed **per fold**, from that fold's own training split — the one
  deliberate methodology change from the single-split ablation, requested
  for this experiment specifically.
- All seven modality subsets from the original ablation are re-run here,
  for a complete confidence-interval version of that table. Full fusion vs.
  CodeBERT-alone is the priority comparison.
- Fold sizes: ~21,785 train / ~5,446 test per fold (class balance ≈11,856
  safe / ≈9,929 vulnerable in train, ≈2,964 safe / ≈2,482 vulnerable in
  test — consistent across all 5 folds, confirming `StratifiedKFold` held
  the class ratio steady).

Total runtime: 257.3s for all 7 subsets × 5 folds (35 XGBoost fits).

## 2. Results: mean ± std across 5 folds, all seven modality subsets

| Subset | #Features | Accuracy | Precision | Recall | F1 | AUC |
|---|---|---|---|---|---|---|
| AST only | 11 | 0.5597 ± 0.0075 | 0.5189 ± 0.0095 | 0.4749 ± 0.0112 | 0.4957 ± 0.0030 | 0.5806 ± 0.0054 |
| Metrics only | 13 | 0.5675 ± 0.0104 | 0.5304 ± 0.0141 | 0.4498 ± 0.0027 | 0.4867 ± 0.0058 | 0.5885 ± 0.0111 |
| AST + Metrics (no CodeBERT) | 24 | 0.5759 ± 0.0048 | 0.5386 ± 0.0061 | 0.4858 ± 0.0082 | 0.5108 ± 0.0059 | 0.6054 ± 0.0076 |
| CodeBERT only | 768 | 0.5799 ± 0.0035 | 0.5404 ± 0.0041 | 0.5236 ± 0.0129 | 0.5318 ± 0.0073 | 0.6244 ± 0.0040 |
| CodeBERT + AST (no metrics) | 779 | 0.5855 ± 0.0033 | 0.5468 ± 0.0032 | 0.5296 ± 0.0139 | 0.5380 ± 0.0082 | 0.6298 ± 0.0046 |
| CodeBERT + Metrics (no AST) | 781 | 0.5854 ± 0.0049 | 0.5467 ± 0.0058 | 0.5287 ± 0.0120 | 0.5375 ± 0.0073 | 0.6308 ± 0.0058 |
| **Full fusion (AST + Metrics + CodeBERT)** | **792** | **0.5923 ± 0.0034** | **0.5552 ± 0.0035** | **0.5308 ± 0.0116** | **0.5427 ± 0.0071** | **0.6369 ± 0.0031** |

Raw per-fold and per-subset numbers (all seven subsets, including accuracy)
are in `results/experiments/cross_validation.json`.

Full fusion has the **highest mean on every single metric** — accuracy,
precision, F1, and AUC — of all seven subsets, and the tightest or
near-tightest spread (lowest std) on precision and AUC. This is a materially
different picture from the single 80/20 split, where full fusion actually
scored *below* CodeBERT-alone on F1.

## 3. Priority comparison: full fusion vs. CodeBERT-alone

| | Full fusion | CodeBERT-only | Difference |
|---|---|---|---|
| F1 (mean ± SE) | 0.5427 ± 0.0032 | 0.5318 ± 0.0032 | **+0.0109** |
| AUC (mean ± SE) | 0.6369 ± 0.0014 | 0.6244 ± 0.0018 | **+0.0125** |

- **F1**: difference = +0.0109, combined SE (√(SE₁² + SE₂²)) = 0.0045 →
  **difference is 2.41× the combined standard error.**
- **AUC**: difference = +0.0125, combined SE = 0.0023 → **difference is
  ~5.5× the combined standard error.**

## 4. Verdict: does full fusion beat CodeBERT-alone by more than ~1 standard error?

**Yes, on both F1 and AUC — this is a real, not-noise difference, and it
resolves the ambiguity the single-split ablation left open.**

A difference of roughly 2 combined standard errors corresponds to
~95% confidence the true difference is nonzero under a normal approximation;
2.41 SE (F1) clears that bar, and 5.5 SE (AUC) clears it by a wide margin.
Both metrics point the same direction — full fusion consistently ahead of
CodeBERT-alone across all 5 folds, not just on average.

This directly overturns what the single 80/20 split suggested. That split's
apparent "CodeBERT-alone slightly ahead on F1" result was itself the noise:
averaging over 5 different train/test partitions shows full fusion actually
wins consistently, by a modest but statistically real margin (≈1 F1 point,
≈1.25 AUC points). The single-split ablation's own caution — "this is
plausibly within ordinary sampling noise... not necessarily a real,
reproducible ranking" — was the right call to make at the time, and
cross-validation is exactly the follow-up that caution called for. It has
now been done, and the answer is: **fusion does help, consistently, once
you average out single-split noise.**

This does **not** mean every incremental modality addition helps
individually — CodeBERT+Metrics (F1 0.5375) is still marginally *below*
CodeBERT+AST (F1 0.5380) and below full fusion, echoing the single-split
finding that adding metrics alone can be a slight net-negative on F1 in
some combinations. But the three-way full fusion configuration specifically
— the one actually shipped in production — is the best performer on every
metric measured here, and the CodeBERT-alone comparison that most directly
tests "is the extra complexity of fusion worth it" comes out clearly in
fusion's favor once cross-validated.

## 5. What this doesn't change

- This experiment still uses the same random, ungrouped stratified split
  methodology (per-fold) as the production baseline and the original
  ablation — it resolves the *modality* question, not the *leakage*
  question. See `docs/GROUPED_SPLIT_RESULTS.md` (Phase 2 of this same
  session) for the commit-aware split, which addresses that separately.
- Random Forest was not re-run under cross-validation (only XGBoost, matching
  the original ablation's scope).
- The app's production 0.26 decision threshold is not re-tuned or re-applied
  here; F1/precision/recall are at XGBoost's default 0.5 cutoff, same
  methodology as the ablation and `train_classifier.py`'s own baseline.

## 6. Reproducing this

```bash
cd src/model
python cross_validation.py
```

Raw results (every fold's individual metrics, not just the mean/std
summary) are saved to `results/experiments/cross_validation.json`.
