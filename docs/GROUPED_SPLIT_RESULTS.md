# Grouped (Commit-Aware) Split Results

Companion to `docs/ML_FORENSIC_AUDIT_PHASE4.md` §5, which flagged a real
leakage exposure but explicitly did not measure it: the production baseline
(`train_classifier.py`, F1=0.5391, AUC=0.6346) uses a plain
`train_test_split(..., stratify=y)` — nothing prevents two rows from the
same commit from landing on both sides of the train/test boundary. With
12,290 distinct commits, mean 2.22 rows/commit, and one commit contributing
588 rows (2.16% of the whole dataset — re-confirmed fresh in
`src/model/verify_commit_grouping.py`, Phase 0 of this session), that is
structurally very likely to happen on a random split. This experiment
measures, for the first time, whether it actually matters.

Produced by `src/model/grouped_split.py` — a new, standalone script that
only reads the already-fused, already-alignment-fixed
`dataset/processed/final_features.csv` and its `commit_id` column (verified
correct against an independent join in Phase 0 — not taken on faith).
**It does not call, import, or modify `extract_ast_features.py`,
`extract_metrics.py`, `fuse_features.py`, `fusion_core.py`, or the alignment
logic in any way.** Nothing in `models/`, `app/predictor.py`'s
`VULNERABILITY_THRESHOLD` (0.26), or the live app was touched.

## 1. Methodology

- `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` on
  `final_features.csv`'s own `commit_id` column, grouping so that **no
  commit's rows can ever be split across a fold boundary**.
- This was not just assumed from the API's contract — verified two
  independent ways in the script itself, both asserted (would raise and
  halt the script if violated, not silently continue):
  1. Per fold, the set of `commit_id` values in train and the set in test
     have **zero intersection** — checked across all 5 folds.
  2. A second, row-level re-check on fold 0 (grouping every row by
     `commit_id` and confirming no commit's rows appear under more than one
     split label) independently confirms the same thing.
  Both checks passed cleanly: **0 commits split across train/test, in
  every fold.**
- Same XGBoost hyperparameters as production: `n_estimators=100,
  max_depth=6, learning_rate=0.1, random_state=42`, `scale_pos_weight`
  computed per fold from that fold's own training split — same
  methodology as `src/model/cross_validation.py` (Phase 1 of this
  session), for direct comparability.
- Full-fusion (792-dim) feature set only — this experiment is about
  whether the *split* changes results, not a re-run of the modality
  comparison (that's Phase 1).
- Compared directly against the production baseline: a single random
  stratified 80/20 split with no commit grouping (F1=0.5391, AUC=0.6346,
  `models/training_metadata.json`, reproduced exactly by
  `modality_ablation.py`'s "Full fusion" row).

Total runtime: 71.0s for all 5 grouped folds.

## 2. Fold composition (grouping worked, and reduced usable groups per test fold as expected)

| Fold | Train rows | Train commits | Test rows | Test commits |
|---|---|---|---|---|
| 0 | 21,784 | 9,839 | 5,447 | 2,451 |
| 1 | 21,785 | 9,832 | 5,446 | 2,458 |
| 2 | 21,785 | 9,830 | 5,446 | 2,460 |
| 3 | 21,785 | 9,829 | 5,446 | 2,461 |
| 4 | 21,785 | 9,830 | 5,446 | 2,460 |

Row counts per fold are almost identical to Phase 1's random `StratifiedKFold`
(as expected — both target the same 80/20-ish split ratio), but note train
commits (~9,830) + test commits (~2,455) ≈ 12,285, close to but not exactly
12,290 total commits per fold split, since `StratifiedGroupKFold` assigns
whole commits to exactly one side. Class balance (safe/vuln counts) was
preserved closely across folds despite the grouping constraint, confirming
`StratifiedGroupKFold`'s stratification worked as intended even with the
588-row outlier commit and other multi-row commits in the mix.

## 3. Results: grouped 5-fold CV, full fusion (792-dim)

| Metric | Mean ± Std | SE |
|---|---|---|
| Accuracy | 0.5417 ± 0.0129 | 0.0057 |
| Precision | 0.4972 ± 0.0147 | 0.0066 |
| Recall | 0.4791 ± 0.0304 | 0.0136 |
| F1 | 0.4876 ± 0.0191 | 0.0086 |
| AUC | 0.5640 ± 0.0130 | 0.0058 |

Per-fold F1 ranged from 0.4738 to 0.5177, and per-fold AUC ranged from
0.5462 to 0.5795 — every single fold scored below the production baseline's
F1 (0.5391) and AUC (0.6346), not just the average.

For context: this grouped-CV fold-to-fold std (F1 std 0.0191) is roughly
**2.7× wider** than Phase 1's random-split CV std on the same full-fusion
feature set (F1 std 0.0071, `docs/CROSS_VALIDATION_RESULTS.md`). Grouped
folds are noticeably less stable fold-to-fold than random folds — itself a
signal that commit-level clustering affects more than just the mean score.

## 4. Direct comparison: grouped split vs. production baseline

| Metric | Baseline (random split) | Grouped CV mean | Difference |
|---|---|---|---|
| Accuracy | 0.5932 | 0.5417 | **-0.0515** |
| Precision | 0.5574 | 0.4972 | **-0.0602** |
| Recall | 0.5219 | 0.4791 | **-0.0428** |
| F1 | 0.5391 | 0.4876 | **-0.0515 (-9.55%)** |
| AUC | 0.6346 | 0.5640 | **-0.0706 (-11.13%)** |

## 5. Finding: performance drops meaningfully when commit-level leakage is removed

**Yes — plainly, this drops, and by a real, not-marginal amount.** F1 falls
by 5.15 points absolute (9.55% relative), AUC falls by 7.06 points absolute
(11.13% relative). Every metric drops. This is not comparing a single
grouped point-estimate against a single baseline point-estimate either —
the grouped CV's own variability is far too small to explain a gap this
size as noise: the baseline F1 (0.5391) is ~6 standard errors above the
grouped mean (F1 SE=0.0086) and ~2.7 per-fold standard deviations above it
(F1 std=0.0191) — either way, well outside the range grouped-fold variation
alone would plausibly produce.

**What this means for the original random-split numbers**: the production
baseline's F1=0.5391 / AUC=0.6346 are real numbers for the *random-split*
evaluation protocol, but they are **not a trustworthy estimate of how the
model performs on genuinely unseen commits** — which is the realistic
deployment scenario (a real user scans a repo whose commits the model has
certainly never seen). Some fraction of the random split's apparent
performance was the model benefiting from having seen near-duplicate or
closely related functions from the *same commit* during training, then
being evaluated on other functions from that same commit at test time. Once
that structural advantage is removed, true held-out performance is
meaningfully lower.

This confirms the leakage concern `docs/ML_FORENSIC_AUDIT_PHASE4.md` §5
raised on structural grounds (12,290 commits, real multi-row skew, no
grouping in the production split) was not just theoretically possible but
**empirically consequential** — a ~9-11% relative performance drop, not a
rounding-level artifact.

## 6. Follow-up: does fusion still beat CodeBERT-alone once leakage is removed?

`docs/CROSS_VALIDATION_RESULTS.md` (Phase 1, random-split 5-fold CV) found
full fusion beats CodeBERT-alone by a real margin: +0.0109 F1 (2.41 combined
SE) and +0.0125 AUC (~5.5 combined SE) — not noise, a genuine advantage for
fusion. The natural question §6 above left open: does that advantage survive
once commit-level leakage is removed, or was some of it itself an artifact
of leakage?

Produced by `src/model/grouped_split_codebert_only.py` — re-runs the
**identical** grouped fold assignment already used for the full-fusion run
above, on the CodeBERT-only (768-dim) subset. "Identical" is not just
asserted — it's verified two ways in the script: (1) `StratifiedGroupKFold`'s
fold assignment is a deterministic function of `y`, `groups`, `n_splits`,
`random_state`, and `shuffle` only (confirmed against the sklearn 1.x
source — `_iter_test_indices` never reads `X`'s values, only its length for
validation), so calling it with the same parameters on the same row order
necessarily reproduces the same folds regardless of which feature columns
are sliced into `X`; and (2) this run's fold row-counts were checked against
`results/experiments/grouped_split.json`'s recorded counts and matched
exactly, fold for fold — confirmed, not assumed.

### Four-way comparison

| Config | Split | F1 | AUC |
|---|---|---|---|
| Full fusion | random (single 80/20) | 0.5391 | 0.6346 |
| Full fusion | grouped (5-fold CV) | 0.4876 | 0.5640 |
| CodeBERT-only | random (single 80/20) | 0.5418 | 0.6309 |
| CodeBERT-only | grouped (5-fold CV) | **0.4861 ± 0.0138** (SE 0.0062) | **0.5465 ± 0.0072** (SE 0.0032) |

### The gap, random split vs. grouped split

| | Full fusion − CodeBERT-only | Combined SE | Ratio |
|---|---|---|---|
| Random-split 5-fold CV (Phase 1) — F1 | +0.0109 | 0.0045 | **2.41×** |
| Random-split 5-fold CV (Phase 1) — AUC | +0.0125 | 0.0023 | **5.48×** |
| Grouped 5-fold CV (this follow-up) — F1 | +0.0015 | 0.0106 | **0.14×** |
| Grouped 5-fold CV (this follow-up) — AUC | +0.0175 | 0.0066 | **2.64×** |

### Honest answer: the gap shrinks substantially, and on F1 specifically it disappears

**Neither "same margin" nor a clean "reverses" is correct — report the
actual, mixed result.**

- **On F1, the fusion-vs-CodeBERT-alone gap collapses into noise.** +0.0109
  (2.41 SE, a real difference under random-split CV) shrinks to +0.0015
  (0.14 SE) under grouping — a ratio close enough to zero that these two
  configurations are **statistically indistinguishable on F1** once
  commit-level leakage is removed. Some of the F1 advantage fusion appeared
  to have was itself inflated by leakage.
- **On AUC, a real edge for fusion survives, but the picture is more mixed
  than the SE ratio alone suggests.** The *absolute* AUC gap actually grew
  slightly under grouping (0.0125 → 0.0175), but its statistical strength
  dropped (5.48 SE → 2.64 SE) because grouped-fold variance is wider than
  random-fold variance for both configurations. 2.64 combined SE is still a
  real, defensible signal (comfortably above the ~2 SE / 95%-confidence
  rule of thumb used throughout this session) — fusion keeps a modest but
  genuine AUC edge under grouping, just not as overwhelming a margin as
  random-split CV suggested.
- **Both configurations drop by roughly the same absolute amount under
  grouping**, relative to each one's own random-split number (full fusion:
  F1 −0.0551, AUC −0.0729 vs. its Phase-1 random-CV mean; CodeBERT-only:
  F1 −0.0557, AUC −0.0844 vs. its original single-split ablation number) —
  leakage inflated both configurations' apparent performance by a similar
  amount, not just fusion's. Fusion's relative F1 *advantage* over
  CodeBERT-alone is what shrinks to nothing, not because CodeBERT-alone
  improved, but because fusion's random-split F1 lead was itself
  substantially a leakage artifact.

**Bottom line for the project's central "does fusion help" claim**: fusion's
case is now weaker than Phase 1 alone suggested, but not eliminated. Once
leakage is removed, don't claim fusion gives a meaningful F1 improvement
over CodeBERT-alone — the honest data says that specific claim is not
supported. A smaller, still-real AUC advantage for fusion does survive
grouping, so "fusion has a modest, defensible edge on the threshold-
independent metric, but not a dependable one on F1" is the accurate
combined statement across Phase 1 and this follow-up — not "fusion clearly
wins" and not "fusion doesn't matter."

## 7. What this doesn't change

- The model, training pipeline, `app/predictor.py`'s 0.26 threshold, and
  everything shipped in the live app are **unchanged** — every experiment
  in this document only measures what the *evaluation number* would look
  like under a stricter, more realistic split. Nothing about the deployed
  model itself was touched.
- This is 5-fold grouped CV (not a single 80/20 grouped split) specifically
  because it was feasible in the time available — a stronger, lower-variance
  estimate than the single-split minimum this task allowed for as a
  fallback.
- §6's follow-up reused the exact same fold assignment as §§1-5's
  full-fusion run for a controlled comparison; it does not re-run the other
  five modality subsets from the original ablation under grouping (AST-only,
  Metrics-only, etc.) — full fusion vs. CodeBERT-alone was the priority
  pair requested, and is the pair reported here.

## 8. Reproducing this

```bash
cd src/model
python grouped_split.py                    # full fusion, grouped split (Sections 1-5)
python grouped_split_codebert_only.py       # CodeBERT-only, same fold assignment (Section 6)
```

Raw results (every fold's individual metrics, train/test commit counts, and
the baseline comparisons) are saved to
`results/experiments/grouped_split.json` and
`results/experiments/grouped_split_codebert_only.json` respectively.
