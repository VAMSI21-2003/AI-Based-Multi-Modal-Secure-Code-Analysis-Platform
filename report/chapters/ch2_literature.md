# CHAPTER 2: LITERATURE SURVEY

## 2.1 Existing Research and Related Work

Automated software vulnerability detection has progressed through three broad, overlapping phases,
each addressed in turn below. Every claim in this section was checked against the original source
before being included; where an earlier internal draft of this project's own documentation
(`paper/research_paper.md`) attributed a specific benchmark number to a paper that, on verification,
did not actually report that number in that form, the claim has been dropped or rephrased rather than
repeated (for example, VulDeePecker predates the Devign dataset by a year and could not have been
"evaluated on Devign," a claim present in an earlier internal draft that this report does not repeat).

**Rule-based static analysis.** Commercial and open-source static analyzers such as Coverity apply
abstract interpretation, dataflow analysis, and pattern matching against a library of known-dangerous
constructs to flag potential defects without executing the program. Bessey et al. (2010), reporting on
Coverity's deployment at industrial scale, documented both the tool's effectiveness at catching common
classes of memory-safety and concurrency defects and the practical cost of maintaining and tuning rule
sets across large, heterogeneous codebases. This family of tools is precise on the specific patterns
its rules encode but, by construction, cannot generalize to defect patterns it has not been explicitly
programmed to recognize — the core limitation this project's learning-based approach is intended to
address.

**Sequence-based deep learning.** The static-analysis limitation above — no generalization beyond the
rule library — is exactly what motivated the shift toward learning from examples instead of hand-coded
patterns. Li et al. (2018) were among the first to show this was practical for vulnerability detection:
their VulDeePecker system cut C/C++ source into "code gadgets" (slices of a program built around
security-relevant API calls) and fed them to a bidirectional LSTM, letting the network discover
vulnerability-indicative patterns on its own rather than being told what to look for. The dataset behind
that result came from NVD and SARD, not from Devign, which did not yet exist. What matters for this
project is the underlying shift VulDeePecker represents — code as a sequence a model can learn from,
rather than only a target for pattern matching — since every learning-based system discussed below,
including this project's own CodeBERT branch, builds on that same shift.

**Graph-based structural learning.** A different line of work argues that flattening a function into a
token sequence throws away information a reviewer would actually use: which branch calls which, how
values flow between statements, how deeply a block is nested. Zhou et al. (2019) built the Devign
benchmark around this argument, merging a function's syntax tree with its control- and data-flow edges
into one graph and letting a Gated Graph Neural Network learn directly over that structure, reporting
sizeable accuracy and F1 gains over the sequence- and rule-based baselines it was compared against, on
real-world functions drawn from FFmpeg and QEMU. That same benchmark — 27,318 functions before this
project's own cleaning step, 27,231 after — is the dataset this project trains and evaluates on
throughout. The underlying argument (structure carries signal a flat token sequence misses) is also why
this project includes an AST-derived feature branch of its own; the difference is that this project
counts structural properties into a fixed-size vector rather than learning a graph representation
end-to-end, trading some of the GNN's expressiveness for a much simpler, cheaper-to-train model.

**Pretrained transformer models for code.** Once BERT (Devlin et al., 2019) showed that a Transformer
pretrained on unlabeled text could be fine-tuned for many downstream natural-language tasks, an obvious
follow-up question was whether the same recipe transfers to source code. Feng et al. (2020) answered it
with CodeBERT: rather than pretrain on natural language alone, they trained on paired code and
documentation spanning six programming languages (6.4 million pairs), combining a masked-language
objective with a second task that asks the model to spot which tokens were swapped for plausible
alternatives — giving the resulting embeddings some sensitivity to code, not just to natural-language
patterns. Lu et al. (2021) later folded a Devign-based defect-detection split into the CodeXGLUE
benchmark suite (21,854/2,732/2,732 train/validation/test functions) and reported that fine-tuning
CodeBERT on the raw token sequence alone — no structural or metric features at all — already reaches
around 62.1% accuracy. This project does not fine-tune CodeBERT; it uses the pretrained `[CLS]`
embedding as a fixed, off-the-shelf semantic feature, and Chapter 7 places this project's own
fused-model result alongside the CodeXGLUE fine-tuned-CodeBERT figure as an external point of
reference.

**Realism of benchmark evaluation.** Chakraborty et al. (2020), in the paper introducing the ReVeal
study ("Deep Learning based Vulnerability Detection: Are We There Yet?"), evaluated several
deep-learning vulnerability detectors on a newly curated, more realistic dataset drawn from the
Chromium and Debian Linux Kernel projects (maintaining a roughly 1:10 vulnerable-to-benign ratio to
reflect real-world class imbalance) and found that reported performance dropped by more than 50%
relative to the same models' performance on earlier, more balanced benchmark datasets. This finding is
directly relevant to how this project's own results are interpreted: the modest F1-score obtained here
(Chapter 7) is consistent with the broader literature's finding that vulnerability detection
performance on curated benchmarks does not transfer cleanly, and a modest score on a real, imbalanced
benchmark is not itself evidence of an implementation defect.

**Line-level and attention-based transformers.** Fu and Tantithamthavorn (2022) proposed LineVul, which
fine-tunes CodeBERT with a line-level attention mechanism and evaluates on a large real-world dataset
of over 188,000 C/C++ functions, reporting substantial improvements in function-level F1 and line-level
localization accuracy over prior graph-based baselines such as IVDetect. LineVul's use of attention
weights to approximate which lines drove a prediction is conceptually related to, but distinct from,
this project's own line-level highlighting feature (Chapter 4/5), which is implemented as a
deterministic, rule-based pattern scanner rather than a model-internal attention signal — a design
choice made explicitly so that the line-level explanation shown to a user in the application does not
overstate what the trained classifier can actually explain about itself.

**Classical software metrics.** McCabe (1976) proposed cyclomatic complexity as a proxy for a
function's error-proneness, and Chidamber and Kemerer (1994) proposed the CK metrics suite for
object-oriented software; both remain foundational references for the general claim, reused in this
project's own metrics branch, that simple structural counts (branches, nesting depth, size) carry
non-trivial signal about defect-proneness even without any learned representation.

## 2.2 Gaps in Existing Systems

Drawing the above together, three gaps motivate this project's design:

1. **Single-modality ceiling.** Sequence-based models (VulDeePecker, CodeBERT/CodeXGLUE) and
   graph-based models (Devign) each report meaningful but individually limited performance, and neither
   family routinely incorporates the other's signal alongside classical software metrics in one
   classifier — most published work evaluates these representations in isolation rather than fused.
2. **Benchmark realism.** As ReVeal's findings show, reported benchmark performance is not a reliable
   predictor of real-world performance; a project that reports only its benchmark F1-score without
   disclosing dataset limitations, class balance, or known implementation issues risks overstating what
   the system can do.
3. **Deployability gap.** The majority of the systems surveyed above are evaluated as offline research
   pipelines (a training script and a reported metric) rather than packaged as an interactive tool a
   developer could actually use during code review — this project explicitly closes that gap by
   building a full FastAPI/React application around the trained classifier, including remediation
   suggestions, an automated patch-and-re-scan loop, and whole-project graph visualizations, none of
   which the surveyed research systems provide.

## 2.3 Overview of Technologies Used

- **CodeBERT** (Feng et al., 2020) — a RoBERTa-architecture Transformer pretrained jointly on source
  code and natural-language documentation; used here purely as a fixed embedding extractor.
- **tree-sitter** — an incremental parser generator (used via its C grammar) that produces a concrete
  syntax tree for each function, traversed by this project to derive the 11 AST-based structural
  features.
- **XGBoost** (Chen and Guestrin, 2016) — a scalable gradient-boosted decision tree implementation,
  used here as the primary classifier trained on the 792-dimensional fused feature vector.
- **Random Forest** (Breiman, 2001) — a bagged decision-tree ensemble, trained here as a comparison
  baseline against XGBoost on the identical feature set and split.
- **FastAPI** and **React/TypeScript** — the web-application layer that serves the trained model and
  presents its output; these are engineering technologies rather than research contributions, and are
  described in full in Chapter 4.

## 2.4 Comparison of Different Approaches

**Table 2.1: Comparison of prior approaches against this project**

| Approach | Representation | Reported metric (as published) | Relationship to this project |
|---|---|---|---|
| Static analysis (Coverity) — Bessey et al. (2010) | Hand-written rules, dataflow/taint analysis | Not reported as a single F1/accuracy figure; evaluated qualitatively at industrial scale | Motivates the need for a learning-based approach; not directly comparable numerically |
| VulDeePecker — Li et al. (2018) | Token sequence (code gadgets), BiLSTM | Evaluated on NVD/SARD-derived data, not Devign | Establishes sequence-based deep learning as viable; predates this project's dataset |
| Devign GNN — Zhou et al. (2019) | Joint AST+CFG+DFG graph, GGNN | Reports large relative F1/accuracy gains over prior baselines on its own dataset | Source of this project's dataset; structural-graph idea reused here as a fixed AST feature vector instead |
| CodeBERT (fine-tuned) — Lu et al. (2021), CodeXGLUE | Token sequence, Transformer | ≈62.1% accuracy on the CodeXGLUE Devign defect-detection split | Reused here as a frozen feature extractor rather than fine-tuned; external reference point for Chapter 7 |
| ReVeal study — Chakraborty et al. (2020) | Various (GGNN + MLP) | >50% relative performance drop on a realistic, imbalanced dataset vs. curated benchmarks | Frames this project's own modest F1 as consistent with known benchmark-to-reality gaps |
| LineVul — Fu and Tantithamthavorn (2022) | Fine-tuned CodeBERT + line attention | Large relative F1 gains over IVDetect on a 188k-function real-world dataset | Related line-level idea; this project's line highlighting is rule-based, not attention-derived |
| **This project** | AST (11) + software metrics (13) + CodeBERT embedding (768) fused, XGBoost/Random Forest | XGBoost: Accuracy 0.5932, F1 0.5391, AUC-ROC 0.6346 (Chapter 7) | Combines all three representation families in one classifier and exposes the result through a full web application |
