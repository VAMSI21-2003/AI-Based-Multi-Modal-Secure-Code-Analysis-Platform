# CHAPTER 3: METHODOLOGY & SYSTEM ANALYSIS

## 3.1 Existing System

### 3.1.1 Overview of Current System

Prior to this project, vulnerability triage for the target class of C/C++ functions relies on one of
two disconnected approaches, discussed in detail in Chapter 2: rule-based static analyzers that match
source code against a fixed library of known-dangerous patterns, and single-modality machine-learning
research systems (sequence-based, e.g. CodeBERT/CodeXGLUE, or graph-based, e.g. the Devign GNN) that
are typically distributed as an offline evaluation script rather than an interactive tool. Neither
approach, on its own, gives a developer (a) a semantic and structural view of the same function
simultaneously or (b) a usable interface for scanning real code, reviewing the result, and acting on a
remediation suggestion.

### 3.1.2 Challenges and Limitations

- Rule-based tools cannot detect vulnerability patterns outside their rule library and require
  continual, codebase-specific rule maintenance (Chapter 2.1).
- Single-modality learned models discard information the other modality would have captured — the
  modality-ablation experiment run for this project (Section 3.2.4) shows structural-features-only
  models trailing CodeBERT-inclusive models by several F1 points on the same data and split.
- Published benchmark numbers do not reliably predict real-world performance (the ReVeal finding,
  Chapter 2.1), so a system that reports only a benchmark score without disclosing dataset limitations
  risks giving a false sense of reliability.
- None of the surveyed prior systems is packaged as a web application with scan history, remediation
  guidance, an automated patch-and-re-scan loop, or whole-project graph visualization — each is a
  research artifact, not a tool a developer could adopt directly.

## 3.2 Proposed System

### 3.2.1 System Architecture

The proposed system has two halves that share code but run on different schedules: an **offline
training pipeline** (run once, ahead of time, to produce the trained model artifacts) and an **online
serving application** (the FastAPI backend and React frontend, which load those artifacts and reuse the
same feature-extraction functions to score new code on demand). Figure 3.1 (Chapter 4) gives the full
architecture diagram; in outline:

```
Devign raw dataset
   -> preprocessing (dedup, null/empty/short-function removal)
   -> three parallel feature-extraction branches:
        - CodeBERT [CLS] embedding (768-d)
        - AST structural features via tree-sitter (11-d)
        - software metrics from source text (13-d)
   -> feature fusion on a stable per-function ID (792-d fused vector)
   -> XGBoost / Random Forest training (80/20 split, seed 42)
   -> trained model artifacts (models/xgboost.json, models/random_forest.joblib)
        |
        v
FastAPI backend (loads artifacts once at startup)
   -> reuses the same extraction functions for a newly submitted function
   -> SQLite-backed scan history, recommendations, auto-patch, graph analysis
        |
        v
React/TypeScript frontend (Scanner, Analysis, Recommendations, AutoPatch,
Dependency/Call/Knowledge graphs, GitHub scan, CI/CD status)
```

### 3.2.2 Features and Functionalities

The functional surface of the deployed application — scanning (single function, batch upload, or
GitHub repository), per-function analysis with feature-contribution and embedding visualization,
rule-based recommendations, automated patch application with re-scoring, and whole-project graph views
— is described in full in Chapter 4 (System Design) rather than repeated here, since that chapter maps
directly onto the actual page-by-page implementation.

## 3.3 Datasets Used

### 3.3.1 Dataset Description

The project uses the **Devign** dataset (Zhou et al., 2019), a collection of C functions drawn from
real-world open-source projects (FFmpeg and QEMU) and labeled for the presence or absence of a
vulnerability at function granularity. The raw dataset (`dataset/raw/function.json`) contains 27,318
functions before this project's own cleaning step.

### 3.3.2 Data Collection Process

The dataset was consumed as-provided (no new data collection was performed as part of this project);
`src/dataset_loader.py` loads the raw JSON and reports class balance and sample composition prior to
any cleaning.

### 3.3.3 Data Preprocessing Techniques

`src/preprocessing/preprocess_dataset.py` applies, in order: a data-quality check, removal of rows with
null/missing fields, removal of exact duplicate functions, removal of empty function bodies, and
removal of abnormally short functions (a minimum-length filter), followed by whitespace normalization.
This leaves **27,231 cleaned samples**, saved to `dataset/processed/devign_cleaned.csv`/`.json` along
with a data-quality report. A `original_id` column is carried through this step specifically so that
every later feature-extraction branch can be joined back to the same underlying function unambiguously
— a design decision that, as Section 3.2.4 below describes, was not present in the project's first
implementation attempt and had to be added as a correction.

## 3.4 Machine Learning Model/Algorithm Selection

### 3.4.1 Algorithm Justification

Two tree-ensemble classifiers were trained on the identical fused feature set and split: **XGBoost**
(gradient-boosted decision trees) and **Random Forest** (bagged decision trees). Tree ensembles were
chosen over an end-to-end deep-fusion network for this feature set because the 792-dimensional input
mixes three heterogeneous feature types (a dense learned embedding, sparse structural counts, and
sparse text-derived metrics) at very different scales and semantics, and gradient-boosted/bagged trees
handle heterogeneous, mixed-scale tabular features natively without requiring feature-specific
normalization or a learned fusion layer. XGBoost was selected as the **primary** model because it
outperformed Random Forest on every reported metric on the held-out test set (Chapter 7 gives the full
table): F1 0.5391 vs. 0.4798, and AUC-ROC 0.6346 vs. 0.5959.

### 3.4.2 Training and Testing Data Split

An 80/20 stratified split (`train_test_split(..., test_size=0.20, random_state=42, stratify=target)`)
was applied once to the 27,231 fused samples, giving 21,784 training rows and 5,447 test rows (test set
composition: 2,964 non-vulnerable / 2,483 vulnerable). The same fixed split and `random_state=42` is
reused across every experiment reported in this document (the main training run, the threshold-search
experiment, and the modality-ablation experiment) so that all reported numbers are directly comparable.

### 3.4.3 Feature Selection and Engineering

Rather than selecting a subset of features, this project fuses all three representations and lets the
tree ensemble's own split-selection process determine feature importance implicitly. To justify this
choice empirically rather than by assumption, a dedicated **modality-ablation experiment**
(`src/model/modality_ablation.py`) trained a fresh XGBoost model, with the identical hyperparameters and
split, on each of seven feature subsets: CodeBERT-only, AST-only, metrics-only, each pairwise
combination, and the full 792-feature fusion. The results are reported honestly rather than framed to
favor the project's own design choice:

| Feature subset | # Features | F1 | AUC-ROC |
|---|---|---|---|
| AST only | 11 | 0.4939 | 0.5757 |
| Metrics only | 13 | 0.4797 | 0.5883 |
| AST + Metrics (no CodeBERT) | 24 | 0.5018 | 0.6076 |
| CodeBERT only | 768 | 0.5418 | 0.6309 |
| CodeBERT + Metrics | 781 | 0.5326 | 0.6328 |
| CodeBERT + AST | 779 | 0.5444 | 0.6327 |
| **Full fusion (this project's design)** | **792** | **0.5391** | **0.6346** |

The honest reading of this table is two-sided. First, it clearly and decisively justifies including
CodeBERT: every CodeBERT-inclusive subset beats every structural-only subset by several F1 and AUC
points, so a purely structural (AST + metrics) system — closer in spirit to a rule-based static
analyzer — would leave real performance on the table. Second, it does **not** decisively show that
fusing all three modalities beats CodeBERT alone: the four CodeBERT-inclusive subsets cluster within
1.2 F1 points and 0.4 AUC points of one another, full fusion has the single highest AUC but not the
single highest F1, and this is a single 80/20 split without cross-validation, so small differences of
this size are plausibly within ordinary sampling noise rather than a reproducible ranking. This project
proceeds with full fusion because it holds the best AUC-ROC (the threshold-independent metric) and
because the architecture is intended to support explanation features (an AST-derived feature-radar
view and a metrics-derived contribution chart in the Analysis page) that a CodeBERT-only model could
not provide — not because the ablation shows an unambiguous fusion win.

### 3.4.4 A discovered and corrected data-alignment defect

During later validation of the trained pipeline, a forensic audit of the fusion step
(`docs/ML_FORENSIC_AUDIT_PHASE4.md`) found that the original implementation of `fuse_features.py`
joined the AST, metrics, and CodeBERT feature tables using each table's own row position rather than a
shared identifier. Because the AST-extraction and metrics-extraction scripts applied slightly different
minimum-length filters when dropping short functions than the CodeBERT-extraction script did, the three
tables' row positions silently drifted apart — the audit measured that 99.35% of fused rows paired the
label and features of one function with the CodeBERT embedding of a different function. Every metric
computed on the resulting model was therefore invalid. The fix, applied in `src/fusion/fusion_core.py`,
threads the `original_id` column introduced during preprocessing (Section 3.3.3) through every
extraction script and joins on that stable key instead of row position; the models were then retrained
on the corrected, correctly aligned feature table. All metrics reported in this document (Chapters 6–7)
are from this corrected run. This is discussed here, in the methodology chapter, rather than only in
the results chapter, because it materially affects how the training/testing pipeline should be
understood: the join key, not only the model or hyperparameters, is part of what had to be validated
before this system's numbers could be trusted.

## 3.5 Feasibility Study

### 3.5.1 Technical Feasibility

All components used — tree-sitter parsing, a pretrained CodeBERT model run in inference-only mode,
and gradient-boosted/bagged tree training on a ~27,000-row, 792-column feature table — run on standard
CPU hardware within the time budgets observed during development (Section 1.6.2); no specialized
infrastructure is required either to reproduce the offline pipeline or to run the FastAPI/React
application.

### 3.5.2 Economic Feasibility

Every component used — the Devign dataset, the pretrained CodeBERT checkpoint, tree-sitter, XGBoost,
scikit-learn, FastAPI, and React — is open-source and free to use; the only cost is the compute time
to run the pipeline and host the application, both of which are modest at this dataset scale.

### 3.5.3 Operational Feasibility

The system is scoped deliberately as a single-operator academic tool (Chapter 1.7) rather than a
multi-tenant production service, which keeps its operational surface — a Docker Compose deployment of
one backend and one frontend container, backed by a local SQLite file — well within what a single
developer or small team can run and maintain without dedicated operations support.
