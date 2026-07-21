# Modality Ablation Results

Companion to `docs/ML_FORENSIC_AUDIT_PHASE4.md` (the fusion-alignment bug) and
`docs/ML_ALIGNMENT_FIX_RESULTS.md` (the fix + corrected baseline). This
experiment answers a question the corrected baseline alone couldn't: **does
multi-modal fusion (AST + metrics + CodeBERT) actually beat the best single
modality on the corrected data, and by how much?**

Produced by `src/model/modality_ablation.py` — a new, standalone script that
only reads the already-fused, already-alignment-fixed
`dataset/processed/final_features.csv` and column-slices it. **It does not
call, import, or modify `extract_ast_features.py`, `extract_metrics.py`,
`fuse_features.py`, `fusion_core.py`, or the alignment logic in any way.**
Nothing in `models/`, `app/predictor.py`'s `VULNERABILITY_THRESHOLD` (0.26),
or the live app was touched — this is a read-then-train-on-a-copy experiment
against a fresh, separate `XGBClassifier` per subset.

## 1. Column boundaries and split, confirmed against the actual files (not assumed)

`final_features.csv` has 797 columns: 5 metadata (`sample_id`, `target`,
`project`, `commit_id`, `func`) + 792 features, in this exact, contiguous
order (verified by loading the real file, not inferred from documentation):

| Group | Count | Columns |
|---|---|---|
| AST | 11 | `n_functions, n_loops, n_if_statements, n_assignments, n_returns, n_pointer_ops, n_function_calls, n_binary_ops, max_depth, n_total_nodes, n_error_nodes` |
| Metrics | 13 | `loc, function_count, loop_count, if_count, return_count, avg_line_length, max_line_length, comment_count, total_lines, blank_lines, nesting_depth, operator_count, pointer_count` |
| CodeBERT | 768 | `embed_000` .. `embed_767` |

This is the identical column-identification logic already used in
`src/model/train_classifier.py` (copied verbatim into the ablation script,
not reimplemented), so "same features" claims are exact, not approximate.

**Split**: one `train_test_split(idx, y, test_size=0.20, random_state=42,
stratify=y)` call on row indices, reused for every modality subset below —
21,784 train / 5,447 test rows (train: 11,856 safe / 9,928 vulnerable; test:
2,964 safe / 2,483 vulnerable). Re-running `train_test_split` a second time
with identical arguments reproduced the exact same indices (asserted in the
script, not just assumed) — the split is genuinely reproducible, so every
subset below trained and tested on **exactly the same rows**.

**Hyperparameters**: `n_estimators=100, max_depth=6, learning_rate=0.1,
random_state=42`, `scale_pos_weight` computed from this same `y_train` for
every subset (so it's identical across all seven runs, exactly as
`train_classifier.py`'s own baseline computes it) — the same values
`train_classifier.py`'s production XGBoost model uses.

## 2. Full-fusion reproduction check (required before trusting anything else)

The "Full fusion" subset (all 792 columns) reproduced the documented
production baseline **exactly** — not approximately:

| Metric | Ablation script | `models/training_metadata.json` (production) |
|---|---|---|
| Accuracy | 0.5932 | 0.5932 |
| Precision | 0.5574 | 0.5574 |
| Recall | 0.5219 | 0.5219 |
| F1 | 0.5391 | 0.5391 |
| AUC-ROC | 0.6346 | 0.6346 |
| Confusion matrix | TN=1935, FP=1029, FN=1187, TP=1296 | TN=1935, FP=1029, FN=1187, TP=1296 |

Every value matches to 4 decimal places and every confusion-matrix cell
matches exactly. This confirms the split, feature columns, and
hyperparameters used here are genuinely identical to the production
baseline — the ablation numbers below are directly comparable to it, not a
separately-trained approximation.

## 3. Results: all seven modality subsets, same split, same XGBoost config

| Subset | #Features | Accuracy | Precision | Recall | F1 | AUC |
|---|---|---|---|---|---|---|
| CodeBERT only | 768 | 0.5891 | 0.5510 | 0.5328 | 0.5418 | 0.6309 |
| AST only | 11 | 0.5568 | 0.5151 | 0.4744 | 0.4939 | 0.5757 |
| Metrics only | 13 | 0.5647 | 0.5270 | 0.4402 | 0.4797 | 0.5883 |
| AST + Metrics (no CodeBERT) | 24 | 0.5757 | 0.5399 | 0.4688 | 0.5018 | 0.6076 |
| CodeBERT + AST (no metrics) | 779 | 0.5937 | 0.5569 | 0.5324 | 0.5444 | 0.6327 |
| CodeBERT + Metrics (no AST) | 781 | 0.5888 | 0.5526 | 0.5139 | 0.5326 | 0.6328 |
| **Full fusion (AST + Metrics + CodeBERT)** | **792** | **0.5932** | **0.5574** | **0.5219** | **0.5391** | **0.6346** |

F1/precision/recall are computed at XGBoost's default 0.5 probability
cutoff (`model.predict()`), **the same methodology `train_classifier.py`'s
own baseline uses** — not the app's separately-tuned 0.26 production
decision threshold (`app/predictor.py`), which was selected in a later,
different experiment (`docs/ML_ALIGNMENT_FIX_RESULTS.md` §7) and isn't
re-applied here. AUC is threshold-independent and unaffected by this either
way.

## 4. Honest reading of what this shows

**Clear and decisive**: structural features alone are meaningfully weaker
than anything that includes CodeBERT. AST-only (F1 0.494) and Metrics-only
(F1 0.480) are the two worst performers; even combining them
(AST+Metrics, F1 0.502) doesn't close the gap to any CodeBERT-inclusive
subset. The smallest CodeBERT-inclusive F1 (CodeBERT+Metrics, 0.533) still
beats the best structural-only combination (AST+Metrics, 0.502) by 3.1
points, and the gap is similar on AUC: the best structural-only AUC
(AST+Metrics, 0.608) is still below the *worst* CodeBERT-inclusive AUC
(CodeBERT only, 0.631). **This
is a real, defensible answer to "why not just use a rule-based/structural
static-analysis tool instead of CodeBERT"**: on this dataset, semantic
(CodeBERT) signal captures something structural features don't, and losing
it costs several F1 points.

**Not clear and not decisive**: whether adding AST+metrics *on top of*
CodeBERT is worth it. The four CodeBERT-inclusive subsets — CodeBERT alone
(F1 0.542), CodeBERT+AST (0.544), CodeBERT+Metrics (0.533), and full fusion
(0.539) — cluster within **1.2 F1 points of each other** and **0.4 AUC
points of each other**. Full fusion has the single highest AUC (0.6346,
the threshold-independent, arguably more principled metric here), but is
*not* the highest F1 — CodeBERT alone and CodeBERT+AST both score higher
F1 than full fusion at this particular threshold. Adding metrics to
CodeBERT alone actually *lowers* F1 slightly (0.542 → 0.533) while adding
AST *raises* it slightly (0.542 → 0.544); adding both together (full
fusion) lands in between. This is a genuinely mixed picture, not a clean
"more modalities always help" story — and that's being reported as
measured, not smoothed over.

**Why these small differences shouldn't be over-read**: this is a single
80/20 split with no cross-validation or bootstrap resampling. A 1.2-point
F1 spread and a 0.4-point AUC spread across four otherwise-similar
CodeBERT-inclusive subsets, on a 5,447-sample test set, is plausibly within
ordinary sampling noise for this kind of split — not necessarily a real,
reproducible ranking. Properly resolving "does fusion actually beat
CodeBERT alone" would need k-fold cross-validation or bootstrap confidence
intervals on the test set, which this experiment deliberately did not do
(out of scope for this task — a single, clean, reproducible split was the
goal here, not a full statistical resolution of small differences).

**Bottom line**: multi-modal fusion is justified relative to *structural-
only* approaches (a real, several-point F1/AUC gap that a rule-based tool
using only AST/metrics-like signals would also be subject to), but this
experiment does **not** show a clear, unambiguous win for full fusion over
CodeBERT alone — the honest statement is "roughly comparable, with fusion
holding a small AUC edge," not "fusion clearly wins." Framing it as a
decisive fusion win would overstate what a single train/test split can
actually support.

## 5. What this doesn't answer (explicitly out of scope here)

- Statistical significance of the small differences among CodeBERT-inclusive
  subsets (would need cross-validation or bootstrap CIs — separate,
  larger experiment).
- Whether the same pattern holds under a grouped/commit-aware split
  (`docs/ML_FORENSIC_AUDIT_PHASE4.md` §5 already flagged plain random
  splitting as a separate, unresolved leakage-exposure question,
  independent of this ablation).
- Random Forest was not re-run per subset (only XGBoost, as requested).
- The app's production 0.26 decision threshold was not re-tuned per
  subset; only default-threshold F1/precision/recall are reported here.

## 6. Reproducing this

```bash
cd src/model
python modality_ablation.py
```

Raw results (including confusion matrices per subset) are also saved to
`results/experiments/modality_ablation.json`.
