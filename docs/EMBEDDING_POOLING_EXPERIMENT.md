# Embedding Pooling Experiment: [CLS] vs. Mean-Pooling

A prior diagnostic (`docs/ML_FORENSIC_AUDIT_PHASE4.md` §16-17) reported that
CodeBERT `[CLS]`-token embeddings on this dataset have a mean pairwise
cosine similarity of **0.9833** across 500 random functions — i.e. the
embedding space is highly anisotropic: almost every function, regardless of
content, projects to nearly the same direction in the 768-dim embedding
space. That number was computed before the fusion/alignment corruption
described in that same audit was fixed, so this experiment first re-verifies
it on the *current, corrected* dataset before asking whether a different
pooling strategy — mean-pooling over all token positions instead of just the
`[CLS]` token — reduces that anisotropy.

Produced by `src/model/embedding_pooling_experiment.py` — a new, standalone
script that reads `dataset/processed/final_features.csv` for the raw `func`
text and loads the real production tokenizer/model via
`ml_bridge.get_codebert()` (the same path `app/predictor.py` uses). **It does
not call, import, or modify `extract_ast_features.py`, `extract_metrics.py`,
`fuse_features.py`, `fusion_core.py`, the alignment logic, `app/predictor.py`,
the production models, or the 0.26 decision threshold.**

## 1. Methodology

- Sampled 500 random functions from `final_features.csv`'s `func` column
  (`random_state=42`), 0 empty/blank.
- Ran each batch (`batch_size=16`, same as production) through the real
  CodeBERT model **once** per batch, `max_length=512, truncation=True,
  padding=True` (dynamic padding, numerically equivalent to production's
  `padding="max_length"` — already verified in
  `src/model/verify_dynamic_padding.py`).
- From that **single** forward pass's `last_hidden_state`, computed **both**
  reductions so the comparison is a clean apples-to-apples change of pooling
  strategy only, not a second independent (and potentially numerically
  divergent) run:
  - `[CLS]`: `last_hidden_state[:, 0, :]` — what `app/predictor.py` actually
    uses today.
  - Mean-pool: `sum(last_hidden_state * attention_mask) / sum(attention_mask)`
    — mean over all real (non-padding) token positions.
- Metric: mean pairwise cosine similarity across all 500×500 pairs
  (124,750 unique pairs, excluding self-pairs), same metric the original
  0.9833 figure used.
- **Meaningful-reduction threshold, fixed before running the experiment**:
  a drop of ≥0.03 in mean pairwise cosine similarity. Chosen because it is
  far outside sampling noise at n=500 and would represent a real geometry
  change, not a cosmetic one — and because the user's instructions
  explicitly conditioned Part 3 (retraining) on the reduction being
  "meaningful," so the bar had to be set in advance rather than picked to
  fit whatever the result turned out to be.
- Total runtime: 202.4s (179.3s of that is the CodeBERT forward pass over
  500 functions on CPU — no GPU available in this environment).

## 2. Part 1: does the 0.9833 figure still hold?

| | Value |
|---|---|
| Previously reported (pre-correction dataset) | 0.9833 |
| This session, fresh forward pass, corrected dataset | **0.9840** |
| Difference | +0.0007 |

**Yes — confirmed, not just trusted.** The figure holds on the current,
alignment-corrected dataset, essentially unchanged (+0.0007, well within
what re-sampling 500 different random functions would explain on its own).
The anisotropy is real and is not an artifact of the earlier data-alignment
bug.

## 3. Part 2: does mean-pooling reduce anisotropy?

| Pooling strategy | Mean pairwise cosine similarity |
|---|---|
| `[CLS]` (production) | 0.9840 |
| Mean-pool (all tokens, attention-mask-respecting) | **0.9642** |
| Reduction | +0.0198 |

Mean-pooling does lower the anisotropy — 0.9642 vs. 0.9840 — but the
reduction (0.0198) is **below the 0.03 meaningful-reduction threshold** set
before running this experiment. The embedding space is still highly
anisotropic either way: even with mean-pooling, essentially any two
functions' embeddings still point in nearly the same direction (cosine
similarity ~0.96). Mean-pooling narrows the effect slightly; it does not fix
it.

This is consistent with published findings on BERT-family models (e.g.
Ethayarajh 2019): anisotropy is a property of the last transformer layer's
output geometry shared across *all* token positions, not something specific
to the `[CLS]` token — so pooling over more of those same anisotropic
positions was never likely to fully resolve it, and it didn't here.

## 4. Part 3: retraining

**Skipped, per instruction.** Mean-pooling did not meet the pre-declared
0.03 meaningful-reduction bar (actual: 0.0198), so no full-dataset
mean-pooled embedding extraction or XGBoost retrain was run. Given the
CodeBERT forward pass took 179s for 500 functions on this CPU-only
environment, a full 27,231-row extraction would have cost roughly 3 hours
for a change that the anisotropy measurement itself gave no reason to expect
would improve F1/AUC over the current `[CLS]`-based production baseline
(F1=0.5391, AUC=0.6346) — not worth spending on a negative-leaning signal.

## 5. Verdict

- The 0.9833 anisotropy figure is **re-confirmed** on the current corrected
  dataset (0.9840, effectively unchanged).
- Mean-pooling is **not a fix** for it — it reduces mean pairwise cosine
  similarity by only ~2 points (0.9840 → 0.9642), well short of a
  meaningful change, and the embedding space remains highly anisotropic
  either way.
- No retraining was performed, and none was warranted by this result.
- This does **not** mean CodeBERT embeddings carry no signal — the
  cross-validation experiment (`docs/CROSS_VALIDATION_RESULTS.md`) already
  showed CodeBERT-alone and full fusion both meaningfully outperform
  AST/metrics-only subsets despite this anisotropy. It does mean the
  semantic branch's contribution is likely capped by this geometry, and
  fixing it (if desired) would need a different intervention — e.g.
  whitening/standardizing the embedding space, or a differently
  fine-tuned/pretrained encoder — not a different pooling strategy over the
  same frozen `microsoft/codebert-base` outputs.

## 6. What this doesn't change

- `app/predictor.py`'s embedding extraction (`[CLS]`, `padding=True`) is
  untouched — this was a read-only, standalone research script.
- The production models, the 0.26 decision threshold, and
  `fuse_features.py`/`fusion_core.py` were not touched.
- `paper/research_paper.md` and `docs/MODALITY_ABLATION_RESULTS.md` were not
  updated.

## 7. Reproducing this

```bash
cd src/model
python embedding_pooling_experiment.py
```

Raw results are saved to `results/experiments/embedding_pooling_experiment.json`.
