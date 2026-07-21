# ML Pipeline — Forensic Audit (Phase 4)

End-to-end audit of `dataset → cleaning → dedup → split → AST → metrics →
CodeBERT → fusion → training → evaluation → artifacts → inference → API → UI`,
performed against the actual code in `src/`, `app/`, `backend/ml_bridge.py`,
and the actual dataset/model files — not assumed from prior notes. Every
number below was freshly measured in this audit unless cited from an existing
artifact (`models/training_metadata.json`, `dataset/notes/*.md`).

## 1. Pipeline stages, as actually implemented

```
dataset/raw/ (Devign: function.json or train/valid/test.jsonl)
  → src/preprocessing/preprocess_dataset.py   (dedup, null/empty/short-function removal, whitespace cleanup)
  → dataset/processed/devign_cleaned.csv       (27,231 rows)
  → src/ast/extract_ast_features.py            (tree-sitter-c, 11 features, sample_id = row position)
  → src/metrics/extract_metrics.py              (13 regex/text-based metrics, sample_id = row position)
  → src/codebert/extract_embeddings.py          (microsoft/codebert-base, 768-dim [CLS], max_length=512)
  → src/fusion/fuse_features.py                  (inner-join on sample_id → final_features.csv, 27,225 rows)
  → src/model/train_classifier.py                (train_test_split 80/20, stratified, random_state=42; RF + XGBoost)
  → models/xgboost.json, models/random_forest.joblib, models/training_metadata.json
  → backend/ml_bridge.py (run_prediction)         (identical extraction + fusion path at inference, same tokenizer settings)
  → backend/routers/*.py → frontend
```

## 2. Data leakage / duplication (audited, measured)

- **Exact-duplicate removal**: `preprocess_dataset.py` drops rows with identical
  `func` text (`drop_duplicates(subset=["func"])`). Measured: 60 of 27,318 raw
  rows (0.22%) — see `dataset/notes/data_quality_report.md`.
- **Near-duplicate check (this audit, new)**: whitespace-normalized hashing on
  `devign_cleaned.csv` (stripping all whitespace before hashing, to catch
  reformatted-but-identical code the exact-match dedup would miss) found
  **30 near-duplicate groups (≈0.11% of the cleaned dataset)**. Manually
  inspected two groups directly: genuine before/after pairs from FFmpeg where
  non-whitespace content is byte-identical but the label differs — real,
  measured **Devign label noise**, not a bug in this pipeline.
- **Train/test split is a plain random stratified split**
  (`train_test_split(..., random_state=42, stratify=y)`), not grouped by
  `project` or `commit_id`. Reconstructing an exact row-level mapping between
  `devign_cleaned.csv` and `final_features.csv` to check whether the 30
  near-duplicate groups straddle the split boundary is unreliable (6 rows are
  dropped between the two stages by AST-parse failures, shifting positional
  `sample_id` alignment), so an exact cross-split count is not claimed here.
  **Bound, not exact figure**: even in the worst case where all 30
  near-duplicate groups split across train/test, that is at most ~30 of 5,445
  test samples (≈0.55% of the test set) — real, disclosed, but not large
  enough to be *the* explanation for F1=0.567.
  **Recommendation (not yet applied)**: a grouped split (`GroupShuffleSplit`
  on `commit_id` or `project`) would eliminate this residual risk entirely
  and is legitimate future work, not an urgent fix given the small bound.

## 3. Class imbalance

Measured on `final_features.csv`: 12,411 vulnerable (45.6%) / 14,820 safe
(54.4%) after cleaning — a mild, not severe, imbalance. Already handled:
`class_weight="balanced"` (Random Forest) and `scale_pos_weight` (XGBoost,
computed per-training-set as `n_safe/n_vuln`). No further rebalancing
(SMOTE, undersampling) is scientifically justified at this imbalance ratio —
the standard cost-sensitive weighting already in place is the appropriate
technique here, not a gap.

## 4. Label quality

Devign's labels are derived from commit-message/patch heuristics, a known
source of noise in the broader vulnerability-detection literature. This
audit's near-duplicate-with-inconsistent-label finding (§2) is direct,
measured evidence of that noise inside this specific dataset copy, not
merely a citation of the general literature concern.

## 5. Token truncation — the most significant new finding in this audit

CodeBERT tokenization uses `max_length=512, truncation=True` identically in
both training (`src/codebert/extract_embeddings.py`) and live inference
(`app/predictor.py`) — consistent, at least, so there's no train/inference
skew. But **measuring actual token counts on a 1,000-function random sample
(seed=42) of the cleaned dataset**:

| | All | Safe (label 0) | Vulnerable (label 1) |
|---|---|---|---|
| Truncated (>512 tokens) | **45.5%** | 43.6% | 47.6% |
| Mean token count | 963 | 922 | 1,008 |
| Median token count | 446 | 424 | 479 |
| P90 / P99 / max | 2,210 / 7,634 / 20,893 | — | — |

**Nearly half of all functions have their CodeBERT semantic representation
built from an incomplete view of the code** — everything past token 512 is
silently discarded before the `[CLS]` embedding is computed. Vulnerable
functions are truncated modestly more often than safe ones (47.6% vs 43.6%),
meaning the embedding branch's information is systematically a little
weaker on exactly the class this platform most needs to detect well.

**This is a stronger, more direct explanation for the CodeBERT branch's
modest measured contribution (ablation: structural-only F1 0.548 → fused
F1 0.567) than the previously-documented embedding anisotropy finding alone.**
Both are real and both matter, but truncation affecting ~46% of inputs is a
larger-magnitude, more actionable limitation. Fixing it properly would mean
either (a) a long-context code embedding model, or (b) chunking long
functions and pooling per-chunk embeddings — both are real future-work items,
not implemented in this pass (see `docs/ML_EXPERIMENTS.md` for what was
actually tried this session).

## 6. Feature normalization

AST (11-dim) and metric (13-dim) features are raw integer/float counts, not
scaled before concatenation with the CodeBERT embedding. **This is not a bug**:
both production models (XGBoost, Random Forest) are tree-based ensembles,
which split on raw feature values and are invariant to monotonic rescaling —
unlike distance-based or linear models, tree ensembles do not need normalized
inputs. No normalization gap exists for the models actually deployed.

## 7. Threshold selection, calibration (this audit's second major activity)

The production pipeline uses the default 0.5 decision threshold implicit in
`model.predict()`. No threshold optimization was previously performed. This
audit ran a proper train/validation/test experiment — see
`docs/ML_EXPERIMENTS.md` §Experiment 1 for the full methodology and result
(headline: F1 0.554 → 0.632 at a validation-selected threshold of 0.32,
evaluated once on the untouched test set). This is the single most impactful,
already-validated lever found in this audit.

## 8. Cross-validation / seed stability

Not evaluated in this pass (would require multiple additional training runs;
noted as a scope limitation, not silently skipped). The existing pipeline
uses a single fixed `random_state=42` train/test split with no k-fold
cross-validation — a real, disclosed methodological gap. Given the dataset
size (27,225 samples), a single split is a defensible-but-not-ideal choice
for a research prototype; 5-fold CV would strengthen the reported metrics'
reliability and is recommended future work.

## 9. Is the current evaluation methodology scientifically valid?

**Yes, with disclosed caveats.** The test set is genuinely held out (not
touched during training or the original hyperparameter choices, which were
fixed by convention rather than tuned). No test-set leakage into training
beyond the small, bounded near-duplicate risk in §2. The one real gap this
audit closes is the *absence* of a validation set for threshold selection —
which this session's threshold experiment now demonstrates the value of,
using a methodology (train/val/test, no test-set peeking) that satisfies the
"do not tune on the test set" requirement exactly.
