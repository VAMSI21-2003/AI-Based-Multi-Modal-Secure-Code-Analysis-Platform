# CHAPTER 1: INTRODUCTION

## 1.1 Project Overview

Software vulnerabilities in C and C++ codebases remain a persistent source of security incidents,
largely because the two dominant families of automated detection techniques each look at code from
only one angle. Rule-based static analyzers match code against known dangerous patterns — unsafe
functions, missing bounds checks, unchecked pointer arithmetic — and are precise on the patterns they
know but blind to anything structurally different. Learning-based approaches built purely on token or
sequence embeddings, on the other hand, capture semantic similarity to previously seen vulnerable code
but have no explicit notion of control flow, nesting depth, or the structural shape of a function.

The **AI-Based Multi-Modal Secure Code Analysis Platform** is built on the premise that these two views
are complementary rather than competing. The platform extracts three independent descriptions of every
analyzed function — a semantic embedding produced by a pre-trained transformer model, a set of
structural features derived from the function's Abstract Syntax Tree (AST), and a set of classical
software-engineering metrics computed directly from the source text — concatenates them into a single
feature vector, and classifies the fused representation with a gradient-boosted tree ensemble. The
resulting model is exposed through a full web application rather than a notebook or command-line
script: a FastAPI backend serves predictions, persists scan history, and performs auxiliary analyses
(dependency graphs, call graphs, a CWE knowledge base, patch suggestion and re-scan), and a React/
TypeScript frontend presents these results across a set of purpose-built pages (a code scanner, a
per-function analysis view, a recommendations view, an automated-patch view, several graph
visualizations, and a GitHub repository scanning mode).

This report documents the complete pipeline as actually implemented and deployed — from the raw Devign
dataset through preprocessing, three-branch feature extraction, feature fusion, model training, and the
FastAPI/React application built on top of the trained model — and reports its measured performance
honestly, including a data-fusion defect that was discovered during a later audit and corrected before
the final models were trained (Section 6.4 and Chapter 7 discuss this in detail).

## 1.2 Statement of the Problem

Given a C/C++ function, determine whether it contains a security vulnerability, using a single model
that combines semantic, structural, and metric-based signals, and deliver that determination through a
usable application rather than only as an offline evaluation script. Single-modality baselines —
either a fine-tuned transformer working on raw token sequences alone, or a graph neural network working
on structural representations alone — each leave out information the other captures; the problem this
project addresses is whether fusing all three signal types into one feature vector, classified by a
conventional ensemble model, is a viable and practical alternative for function-level vulnerability
triage, and what such a system looks like as a deployable tool rather than a research script.

## 1.3 Brief Description of the Project

The project is organized around a linear offline pipeline and an online serving application built on
top of its output:

- **Data preparation.** The Devign dataset (function-level C/C++ code labeled vulnerable/not-vulnerable)
  is cleaned — null values, duplicates, empty functions, and abnormally short functions are removed —
  leaving 27,231 usable samples.
- **Three-branch feature extraction.** Every retained function is independently converted into (a) a
  768-dimensional CodeBERT `[CLS]` embedding, (b) an 11-dimensional AST feature vector obtained by
  parsing the function with tree-sitter's C grammar and traversing the resulting syntax tree, and
  (c) a 13-dimensional set of software metrics (line counts, branching/looping counts, nesting depth,
  operator and pointer usage, comment density) computed directly from the source text.
- **Feature fusion.** The three branches are joined on a stable per-function identifier into a single
  792-dimensional feature vector per function.
- **Model training.** XGBoost and Random Forest classifiers are trained on an 80/20 stratified split
  (21,784 train / 5,447 test, `random_state=42`); XGBoost is selected as the primary model on the basis
  of its higher F1-score and AUC-ROC (Chapter 3.2.2 and Chapter 7 give the full comparison).
- **Application layer.** A FastAPI backend loads the trained model once at startup, reuses the same
  feature-extraction code for live requests, persists every scan to a local SQLite store, and exposes
  it through a React frontend with dedicated pages for scanning, per-function analysis, remediation
  recommendations, automated patch application with re-scanning, dependency/call/knowledge-graph
  visualization of a whole uploaded project, and direct scanning of a public GitHub repository.

## 1.4 Objectives of the Project

1. Build a reproducible offline pipeline that extracts semantic (CodeBERT), structural (AST), and
   metric-based features from C/C++ functions and fuses them into a single representation.
2. Train and compare tree-ensemble classifiers (XGBoost, Random Forest) on the fused representation and
   select the better-performing model using standard classification metrics (accuracy, precision,
   recall, F1-score, AUC-ROC, confusion matrix).
3. Package the trained pipeline behind a FastAPI service that can score both a single pasted function
   and a batch of uploaded files or an entire cloned GitHub repository.
4. Present the results through a React web interface that goes beyond a bare verdict — showing
   per-feature contribution, an embedding-space visualization, rule-based secure-rewrite suggestions,
   an automated patch-and-re-scan loop, and whole-project graph views (file dependencies, cross-file
   call graphs, and a unified knowledge graph linking files, functions, CWE entries, and predictions).
5. Verify every reported number against the project's own trained-model artifacts rather than
   carrying forward earlier, pre-training placeholder figures, and disclose the feature-fusion
   correction that was required to reach the final reported metrics.

## 1.5 Scope of the Project

The system operates at **function-level granularity** on **C/C++ source code** drawn from the Devign
dataset's distribution (real-world functions collected from open-source C/C++ projects). It classifies
a function as vulnerable or not-vulnerable and estimates a probability/confidence for that verdict; it
does not attempt to localize the vulnerability to a specific line with certainty (the line-level
highlighting in the application is a separate, deterministic pattern scanner used as a corroborating
signal, not the ML model's own explanation) and does not cover languages other than C/C++. The
GitHub-scanning mode operates on public repositories only, clones a bounded number of recent commits,
and is explicit in its UI about which files were skipped and why, rather than silently presenting a
partial scan as a complete one. The project targets a single-operator, academic deployment (no
multi-user authentication layer) rather than a multi-tenant production security product.

## 1.6 Software and Hardware Requirements

### 1.6.1 Software Specifications

**Table 1.1: Software stack and verified versions**

| Layer | Technology | Verified version (from the repository's own dependency manifests) |
|---|---|---|
| ML pipeline | Python | 3.11 (CI) / 3.13 (development) |
| ML/feature libraries | PyTorch, Transformers (CodeBERT), XGBoost, scikit-learn, tree-sitter | torch 2.12.0, transformers 5.12.0, xgboost 3.2.0, scikit-learn 1.9.0, tree-sitter 0.25.2, tree-sitter-c 0.24.2 |
| Backend API | FastAPI, Uvicorn, SQLAlchemy, Pydantic | fastapi 0.139.0, uvicorn 0.49.0, SQLAlchemy 2.0.51, pydantic 2.13.4 |
| Backend persistence | SQLite (file-based, via SQLAlchemy) | — |
| Report/export generation | ReportLab, python-docx, python-pptx | reportlab 5.0.0, python-docx 1.2.0, python-pptx 1.0.2 |
| Frontend | React, TypeScript, Vite, Tailwind CSS | react 19.2.7, tailwindcss 4.3.2 |
| Frontend visualization | Recharts, @xyflow/react (graphs), Monaco Editor, dagre (graph layout) | recharts 3.9.2, @xyflow/react 12.11.2, @monaco-editor/react 4.7.0 |
| Containerization | Docker, Docker Compose | backend + nginx-served frontend services |
| CI/CD | GitHub Actions | backend validation, frontend validation, security scan on PR diffs, status aggregation |
| Version control | Git / GitHub | — |

### 1.6.2 Hardware Specifications

- **Development/training machine:** a standard multi-core workstation is sufficient; CodeBERT embedding
  extraction and XGBoost/Random Forest training on ~27,000 samples do not require GPU acceleration,
  though a GPU accelerates the CodeBERT embedding pass. [REQUIRES VERIFICATION: exact CPU/RAM/GPU
  specification of the machine used, if the university requires it stated precisely.]
- **Deployment target:** the containerized backend requires enough memory to hold the loaded CodeBERT
  model, the XGBoost/Random Forest artifacts, and the tree-sitter parser simultaneously; the health
  check in `docker-compose.yml` allows a start-up grace period of over three minutes to accommodate the
  first CodeBERT model load.

## 1.7 Functional and Non-Functional Requirements

**Functional requirements:** accept a single pasted function, a batch of uploaded files/folders/zip
archives, or a public GitHub repository URL as input; return a verdict, probability, confidence, and
model identity for each analyzed function; persist every scan for later retrieval, comparison, and
export; provide remediation recommendations and, where a safe automated rewrite is possible, apply the
patch and re-score the result; visualize a multi-file project's dependency structure, call graph, and a
combined knowledge graph; expose the same functionality through a documented REST API and through a
CI/CD security-scan job that runs the real pipeline against changed files in a pull request.

**Non-functional requirements:** the platform is designed for a single-operator academic/research
context and therefore deliberately omits a multi-user authentication layer (a documented scope decision
in the project's own README, not an oversight); it aims for the first-request latency penalty (model
loading) to be paid once at startup rather than per request, via a `lifespan` pre-warming hook in the
FastAPI application; scan results and history are persisted locally rather than requiring an external
database service; the security-scan CI job is configured to run as a non-blocking, best-effort check by
default so that it augments rather than gates the development workflow.

## 1.8 Company/Domain Profile

Not applicable — this is an independent academic project developed and submitted as part of the MCA
program at the School of Computer Applications, Dayananda Sagar University, and is not undertaken on
behalf of, or in collaboration with, an external company.
