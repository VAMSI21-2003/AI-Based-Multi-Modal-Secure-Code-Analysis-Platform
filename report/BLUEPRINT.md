# Report Blueprint — AI-Based Multi-Modal Secure Code Analysis Platform

Status checkpoint after Phases 1–5. If this session is interrupted, resume from here — do not
re-derive Phases 1–4; read this file plus `report/FORMAT_SPEC.md` first.

Progress: Phase 1 (format) ✅ · Phase 2 (app inventory) ✅ · Phase 3–4 (dataset/model/results
verification) ✅ · Phase 5 (this blueprint) ✅ · Phase 6 (write content) ✅ — all 8 chapters +
references drafted in `report/chapters/` (ch1_introduction.md … ch8_conclusion.md, references.md) ·
Phase 7 (screenshots) — NOT STARTED · Phase 8 (consistency audit) — NOT STARTED ·
Phase 9 (final DOCX assembly) — NOT STARTED.

Also produced during Phase 6/7 prep: `report/figures/confusion_matrix_xgboost.png` and
`report/figures/roc_curve.png`, generated from the real committed model artifacts (reproduced the
production 80/20 split and got an exact AUC match to training_metadata.json) since the project's own
`results/06_confusion_matrix.png`/`08_roc_curve.png` were stale and `analyze_results.py` has a
pre-existing (unrelated) ZeroDivisionError bug in its confusion-matrix section. `results/01_model_
comparison.png` through `05_f1_score.png` were also regenerated (real data, confirmed matching) as a
side effect of running that script. Full backend+frontend test suite was run for real: 119/119 passing
(Chapter 6).

## Title (use everywhere, no exceptions)
**AI-Based Multi-Modal Secure Code Analysis Platform**
(Old/retired title "Multi-Modal Code Vulnerability Detection Using CodeBERT and Structural Code
Analysis" appears in `paper/project_report_part1.md`, `paper/project_report_part2.md`, git history,
and `sonar-project.properties` (last committed version) — that's expected historical context, not to
be reproduced in the new report.)

## Ground-truth facts locked in (do not re-derive, do not use conflicting numbers from elsewhere)

**Source of truth for all ML numbers:** `models/training_metadata.json` and
`models/ml_baseline_status.json`, corroborated by `paper/research_paper.md` (which carries its own
correction erratum dated 2026-07-21/07-22) and `docs/ML_FORENSIC_AUDIT_PHASE4.md` /
`docs/ML_ALIGNMENT_FIX_RESULTS.md`.

- Dataset: Devign (C/C++ function-level vulnerability labels). Raw: `dataset/raw/function.json`.
  Cleaned: 27,231 samples (`dataset/processed/devign_cleaned.csv/json`).
- Features: 792 total = 11 AST (`src/ast/extract_ast_features.py`) + 13 software metrics
  (`src/metrics/extract_metrics.py`) + 768 CodeBERT `[CLS]` embedding
  (`src/codebert/extract_embeddings.py`, `microsoft/codebert-base`). Fused in
  `src/fusion/fusion_core.py` via a stable `original_id` join → `dataset/processed/final_features.csv`
  (797 columns: metadata + 792 features).
- Split: 80/20 stratified, `random_state=42` → 21,784 train / 5,447 test.
- Models trained: XGBoost (100 trees, max_depth=6, lr=0.1, scale_pos_weight) and Random Forest
  (100 trees, class_weight="balanced"). Both in `src/model/train_classifier.py`.
- **Final selected model for reporting as primary: XGBoost** (higher F1/AUC than RF) — present RF as
  the comparison baseline, not co-primary.
- **Final real metrics (use these and only these):**
  | Model | Accuracy | Precision | Recall | F1 | AUC-ROC | PR-AUC |
  |---|---|---|---|---|---|---|
  | XGBoost | 0.5932 | 0.5574 | 0.5219 | 0.5391 | 0.6346 | 0.6223 |
  | Random Forest | 0.5721 | 0.5380 | 0.4329 | 0.4798 | 0.5959 | 0.5635 |
  Confusion matrices (test set, n=5,447): XGB tn=1935 fp=1029 fn=1187 tp=1296; RF tn=2041 fp=923
  fn=1408 tp=1075.
  Decision threshold (F1-maximizing, chosen on a validation carve-out, never on test):
  **0.26** (`src/model/threshold_experiment.py`).
- **Do NOT use** Accuracy 84.00% / Precision 81.52% / Recall 83.33% / F1 0.8242 / AUC 0.998 — these
  are pre-training illustrative placeholder numbers from `paper/project_report_part1.md`,
  `project_report_part2.md`, and `paper/results_section.md` (the latter self-labels them as
  "illustrative estimates"). They must not appear anywhere in the final report.
- **Preliminary/dev-only run, explicitly not a final result:** `dataset/notes/codebert_features.md`
  documents a "demo mode — first 200 samples, no dataset required" smoke-test run of the embedding
  script during development. This is a dev sanity check, not an experiment, and must not be
  confused with or presented alongside the 27,231-sample final run.
- **Known, disclosed issue (this is a legitimate methodology point, not a flaw to hide):** the
  original feature-fusion join used row position instead of a stable key, mispairing ~99.35% of
  fused rows; this was found in a later audit (`docs/ML_FORENSIC_AUDIT_PHASE4.md`), fixed via the
  `original_id` join, and the models retrained on 2026-07-21. `paper/research_paper.md`'s own erratum
  is the cleanest existing prose for this — [OPEN QUESTION for user, see below] on how much of this
  correction narrative to surface in Chapters 6/7.
- Modality ablation (AST-only / Metrics-only / CodeBERT-only / pairwise / full fusion) exists in
  `docs/MODALITY_ABLATION_RESULTS.md` and `src/model/modality_ablation.py` — usable for Chapter 7.2
  "Model Comparisons" if we want to justify *why* fusion (vs. single modality) was chosen.

## Actual system architecture (supersedes the old Streamlit assumption)

- **`app/`** — original ML pipeline library (predictor.py, utils.py: feature extraction, model
  loading, prediction). `app/app.py` is a retired Streamlit prototype, not part of the live product.
- **`backend/`** — FastAPI ("AI Secure Code Analysis Platform API"), imports `app/`'s ML functions via
  `ml_bridge.py`, adds SQLite persistence (`ScanRecord`, `GitHubBatchMeta` via SQLAlchemy), 17 routers
  (scan, dashboard, history, analytics, knowledge, report, intelligence, system, comparison, project,
  research, copilot, patches, export, watch, github, gamification, search).
- **`frontend/`** — React 19 + TypeScript + Vite + Tailwind v4 + Recharts + `@xyflow/react` + Monaco.
  ~40 routed pages; core ones for the report: Scanner, Analysis, Recommendations, AutoPatch,
  DependencyGraph, CallGraphExplorer, KnowledgeGraph, GitHubMode, PlatformHub (CI/CD tab).
- **Deployment:** Docker Compose (backend + nginx-served frontend), GitHub Actions CI/CD
  (backend-validation, frontend-validation, security-scan running the real ML pipeline on PR diffs,
  final-status).
- Full page-by-page functional descriptions are already captured in this session's Phase 2 research —
  reuse verbatim when writing Chapter 4 (System Design) and Chapter 7.5 (Screenshots).

## Chapter-by-chapter content mapping (against `report/FORMAT_SPEC.md`'s official structure)

1. **CHAPTER 1: INTRODUCTION** — Project Overview (what the platform does, why multi-modal),
   Statement of the Problem (single-modality detectors miss either semantic or structural signal),
   Objectives, Scope (C/C++ Devign-scope function-level detection; explicitly note what's out of
   scope), Software/Hardware Requirements (Python 3.11/3.13, Node 20, FastAPI, React, Docker; from
   `backend/requirements*.txt`, `frontend/package.json`), Functional/Non-Functional Requirements
   (scan modes, no-auth single-operator scope per README, performance targets), 1.4 Company/Domain
   Profile — **Not Applicable** (academic project, no external company).

2. **CHAPTER 2: LITERATURE SURVEY** — Existing research on vulnerability detection (traditional static
   analysis, GNN-based Devign baseline (F1 0.561), fine-tuned CodeBERT (F1 0.628) — both cited in
   `paper/research_paper.md`'s comparison), gaps (single-modality limitations), technology overview
   (CodeBERT/transformers, AST parsing via tree-sitter, ensemble tree models), comparison table.
   **[REQUIRES VERIFICATION]**: exact citations (authors/year/venue) for the Devign paper and any
   CodeBERT paper referenced — must pull real bibliographic details before citing, not invent them.

3. **CHAPTER 3: METHODOLOGY & SYSTEM ANALYSIS** — Existing system (single-modality tools, manual
   review), proposed system (multi-modal fusion architecture + web platform), dataset (Devign,
   27,231 cleaned samples), preprocessing (11-step pipeline, `preprocess_dataset.py`), model selection
   (why XGBoost — better F1/AUC than RF on this fused feature set — and why tree ensembles over deep
   fusion networks for this scope), train/test split (80/20, seed 42), feature engineering (792-dim
   fusion), feasibility study (technical/economic/operational — all straightforward for a
   single-operator academic tool).

4. **CHAPTER 4: SYSTEM DESIGN AND DEVELOPMENT** — High-level architecture (source → preprocessing →
   3-branch feature extraction → fusion → XGBoost/RF → FastAPI → React UI), component diagram
   (backend routers ↔ ml_bridge ↔ app/ ↔ frontend pages), DFD, use-case diagram (upload code → scan →
   view analysis → view recommendations → apply patch → re-scan), database design (ScanRecord,
   GitHubBatchMeta schemas — this is the closest thing to "ER diagram" here, note in the report that
   persistence is a lightweight SQLite scan-history store, not a transactional business DB), UI screens
   (Scanner/Analysis/Recommendations/AutoPatch/graphs/GitHub/CI-CD — screenshots go here and in 7.5),
   API design (real FastAPI route table from Phase 2 research), module description (one subsection per
   backend module: scan_service, recommendations, auto_patch, github_service, etc.).

5. **CHAPTER 5: IMPLEMENTATION & CODING** — Languages/frameworks (Python/FastAPI, TypeScript/React),
   algorithmic approach (feature extraction algorithms, XGBoost training procedure, threshold
   selection), pseudocode/flowcharts for the fusion pipeline, code snippets (extraction functions,
   `ml_bridge.py` prediction flow, AutoPatch apply-and-rescan logic since it's a distinctive feature),
   key functionalities (line-risk heatmap scanner, approximate SHAP contribution, PCA embedding
   scatter — all real, all described accurately as heuristic/approximate where the code itself says so).

6. **CHAPTER 6: SOFTWARE TESTING** — Testing strategy (backend pytest suite — 14 test files incl.
   patch/regression tests per git log "Add per-function inference regression tests (7 tests)";
   frontend Vitest), unit/integration/system testing, sample test cases (need to pull 2–3 real test
   names from `tests/`/`backend/tests/` — **[TODO in Phase 6]** read actual test files for concrete
   examples rather than inventing test case names), performance metrics — confusion matrix,
   precision/recall/F1 **using the real numbers above**, and here is the natural place to disclose the
   fusion-bug-found-and-fixed methodology story if the user wants it told (see open question below).

7. **CHAPTER 7: RESULTS AND DISCUSSION** — Experimental setup (hardware/software used to train —
   **[REQUIRES VERIFICATION]**: actual training machine specs if the user wants them stated, otherwise
   describe generically), hyperparameters (listed above), model performance analysis (train vs test,
   bias-variance — note the modest 59.3%/53.9% F1 as a genuine, disclosed limitation rather than
   inflating it), model comparison (XGBoost vs RF, and vs. modality-ablation single-branch models from
   `docs/MODALITY_ABLATION_RESULTS.md`), comparison with existing systems (vs. Devign GNN baseline and
   fine-tuned CodeBERT — the honest, already-written comparison in `paper/research_paper.md`),
   visualization of results (reuse the 8 real charts in `results/01..08_*.png` if they reflect the
   corrected/final run — **[TODO Phase 6]** confirm these PNGs were regenerated after the fusion fix,
   not left over from the buggy run), screenshots of the working system (Phase 7 of this workflow).

8. **CHAPTER 8: CONCLUSION AND FUTURE ENHANCEMENTS** — Conclusion (multi-modal fusion platform built
   and deployed; performance is modest and CodeBERT embedding anisotropy is identified as the likely
   ceiling per `paper/research_paper.md`'s diagnostic — an honest conclusion, not an inflated one),
   limitations (embedding anisotropy, function-level-only granularity, C/C++ only, modest F1), future
   enhancements (the project's own `docs/OPTIMIZATION_SUGGESTIONS_DESIGN.md`,
   `docs/REMEDIATION_ENGINE_PLAN.md`, `docs/ML_IMPROVEMENT_PLAN.md` already contain real forward-looking
   ideas to draw from instead of inventing generic ones).

**REFERENCES** — Devign paper, CodeBERT paper, tree-sitter, XGBoost paper, FastAPI/React docs.
**[REQUIRES VERIFICATION]**: pull exact citation details (real DOIs/venues) before finalizing — do not
fabricate.

## Decisions received from user (2026-07-24) — resolved, do not re-ask

1. **Personal/administrative details** (student name, USN, guide, submission date): user chose to
   leave these as bracketed `[REQUIRES VERIFICATION]` placeholders in the cover/certificate/declaration
   for the user to fill in themselves before submission. Do not invent values for these.
2. **Fusion-bug correction narrative**: user chose to **tell the correction story**. Chapters 6–7 (and
   Ch.3 methodology, briefly) should note that a feature-fusion alignment bug was found via forensic
   audit and fixed before final training, framing the modest F1 0.5391 as the outcome of rigorous
   validation rather than a hidden weakness. Base this narrative on `paper/research_paper.md`'s own
   erratum and `docs/ML_FORENSIC_AUDIT_PHASE4.md` / `docs/ML_ALIGNMENT_FIX_RESULTS.md` — write it fresh
   in report language, don't copy their prose verbatim.
3. **`sonar-project.properties`**: restored via `git checkout --` on 2026-07-24. Resolved, no longer an
   open item.

## `results/*.png` chart audit — resolved

- `results/01_model_comparison.png` … `08_roc_curve.png` (all dated Jun 14) are **stale/pre-fix** —
  do not use them.
- `results/model_comparison.png` and `results/feature_importance.png` (both dated Jul 21, same day as
  the fusion fix) were visually verified against `models/training_metadata.json` and match exactly
  (XGBoost 0.593/0.557/0.522/0.539, RF 0.572/0.538/0.433/0.480; feature importance chart shows
  `blank_lines`/`avg_line_length` (metrics) and `n_total_nodes` (AST) outranking most individual
  CodeBERT embedding dimensions). **These two are safe to use as report figures.**
- **Still missing**: a current confusion-matrix chart and ROC-curve chart. Must generate these fresh
  in Phase 9 from the real confusion-matrix values and AUC already in `training_metadata.json`
  (tn/fp/fn/tp given above) — do not reuse the stale `06_confusion_matrix.png`/`08_roc_curve.png`.

## Next steps once the above is resolved
Phase 6: write chapter content section by section using only the verified facts above. Phase 7: run
the app (`docker-compose up` or local dev servers) and use Claude in Chrome to capture real screenshots
of Scanner, Analysis, Recommendations, AutoPatch, one graph page, GitHub scan, and the CI/CD tab.
Phase 8: consistency audit (title/terms/numbers/figure-numbering). Phase 9: assemble the final DOCX
against `report/FORMAT_SPEC.md` and this blueprint.
