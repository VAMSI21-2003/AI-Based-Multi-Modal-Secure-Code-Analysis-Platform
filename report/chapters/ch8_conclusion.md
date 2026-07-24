# CHAPTER 8: CONCLUSION AND FUTURE ENHANCEMENTS

## 8.1 Conclusion

This project set out to determine whether fusing semantic (CodeBERT), structural (AST), and
software-metric features into a single classifier is a viable approach to function-level C/C++
vulnerability detection, and to deliver that approach as a usable application rather than only an
offline research script. Both parts of that goal were achieved, with results reported honestly rather
than optimistically. The offline pipeline — preprocessing, three-branch feature extraction, fusion, and
XGBoost/Random Forest training — produces a working classifier (XGBoost: Accuracy 0.5932, F1 0.5391,
AUC-ROC 0.6346 on a 5,447-function held-out test set), and the modality-ablation experiment
(Chapter 3.4.3/7.2.3) gives a clear, evidence-based answer to why CodeBERT is included (structural
features alone trail by several F1 points) while being equally honest that full fusion's advantage over
CodeBERT alone is small and not statistically decisive from a single train/test split. The application
layer — a FastAPI backend and React frontend providing scanning, per-function analysis, remediation
recommendations, an automated patch-and-re-scan loop, and whole-project graph visualization — is real
and functioning, verified in this report against the actual routes, pages, and database schema rather
than assumed from an earlier, outdated project description.

The project's final reported metrics are more modest than an earlier, pre-training draft of this same
project's documentation projected, and that gap has a specific, disclosed cause: a feature-fusion
row-alignment defect that mispaired 99.35% of training rows, found by a later forensic audit and
corrected before the final models were trained (Chapter 3.4.4, Chapter 7.3). Reporting this correction
explicitly, rather than presenting only the corrected number without its history, is treated in this
report as itself a demonstration of methodological rigor — a system whose developer can find and fix
this class of silent data-integrity defect, and add a permanent regression test against it
(`tests/test_fusion_alignment.py`), is more trustworthy than one whose only reported number cannot be
independently reproduced from its own artifacts. Every metric in this report was, in fact, independently
re-derived from the committed model artifacts during report preparation (Chapter 7.1.1) and matched
exactly, which is itself evidence that the corrected pipeline is now reproducible.

## 8.2 Limitations of the Project

- **Modest absolute performance.** An F1 of 0.5391 and a recall of 0.5219 mean the model still misses
  close to half of the truly vulnerable functions in the test set; it is not, on its own, a substitute
  for expert code review.
- **CodeBERT embedding anisotropy.** This project's own diagnostic analysis (`paper/research_paper.md`)
  measured a mean pairwise cosine similarity of 0.9833 across a random sample of 500 Devign functions'
  CodeBERT `[CLS]` embeddings — i.e., nearly any two functions in this dataset produce near-identical
  embedding vectors under this representation. This is a plausible ceiling explanation for why adding
  structural/metric features on top of CodeBERT does not yield a larger, unambiguous improvement
  (Chapter 3.4.3): if the semantic embedding itself carries limited discriminative spread, the fusion
  step has less complementary room to exploit.
  ​ [REQUIRES VERIFICATION if reused verbatim: figure re-quoted from the project's own prior
  documentation, not independently re-measured for this report.]
- **Function-level, C/C++-only scope.** The system does not localize a vulnerability within a function
  with model-backed confidence (the line-level highlighting is a separate, deterministic pattern
  scanner, Chapter 4.3.1/5.2.4) and does not generalize to other languages. More broadly, a Devign-only
  evaluation is itself subject to the benchmark-to-reality gap the ReVeal study documents (Chapter 2.1)
  for this class of system generally.
- **Single train/test split.** Every headline number in this report (Chapter 7) comes from one 80/20
  split; no cross-validation or bootstrap confidence interval has been computed, so small differences
  between configurations (e.g. the 1.2 F1-point spread among CodeBERT-inclusive modality subsets,
  Chapter 3.4.3) should not be over-interpreted as reliably reproducible rankings.
- **No multi-user authentication layer.** A deliberate scope decision (Chapter 1.7) appropriate to this
  project's single-operator academic context, but a real gap if the platform were ever deployed beyond
  that context.

## 8.3 Scope for Future Enhancements

The project's own internal planning documentation (`docs/ML_IMPROVEMENT_PLAN.md`) already lays out a
concrete, prioritized set of next steps, reused here rather than invented fresh:

1. **k-fold cross-validation.** Replace the single 80/20 split's point-estimate metrics with
   `StratifiedKFold(n_splits=5)` mean ± standard deviation for F1/Precision/Recall/AUC, to determine
   whether the small differences observed among feature-subset configurations (Chapter 3.4.3) are
   statistically meaningful or sampling noise.
2. **Project- or commit-aware splitting.** The current split is a random stratified split over
   individual functions; because the dataset draws from only two source projects (FFmpeg and QEMU),
   a grouped split by `commit_id` (once the number of distinct commits is confirmed sufficient) would
   test whether the model generalizes across commits rather than partially memorizing project-specific
   patterns.
3. **Feature redundancy analysis.** A correlation matrix over the 11 AST and 13 metric features (small
   enough to inspect directly) to identify and potentially prune redundant structural/metric features.
4. **Addressing embedding anisotropy.** Investigating alternative CodeBERT pooling strategies (e.g.
   mean-pooling over tokens instead of the `[CLS]` vector) or a fine-tuned rather than frozen embedding,
   to test whether the anisotropy limitation identified in Section 8.2 can be reduced.
5. **Application-layer extensions** already scoped in the project's own design documents
  (`docs/REMEDIATION_ENGINE_PLAN.md`, `docs/OPTIMIZATION_SUGGESTIONS_DESIGN.md`) — broadening the
  rule-based automated-patch and optimization-suggestion coverage beyond the current pattern set.
