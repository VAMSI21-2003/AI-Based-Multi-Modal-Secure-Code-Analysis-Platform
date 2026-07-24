# CHAPTER 5: IMPLEMENTATION & CODING

## 5.1 Programming Language and Framework Used

The offline ML pipeline and the FastAPI backend are implemented in **Python** (3.11 in CI, 3.13 in
development); the frontend is implemented in **TypeScript** on **React 19** via **Vite**. Key libraries
are listed with their exact pinned versions in Chapter 1.6.1. The project deliberately reuses one code
path for both training-time and serving-time feature extraction (`app/utils.py`, `app/predictor.py`)
rather than maintaining a separate "production" reimplementation of the pipeline, so that a prediction
made by the web application is guaranteed to use the same feature computation the model was evaluated
on.

## 5.2 Algorithmic Approach

### 5.2.1 AST Feature Extraction (Pseudocode)

```
function extract_ast_features(code):
    counts <- {feature_name: 0 for each of the 11 AST feature names}
    tree <- tree_sitter_C_parser.parse(code)
    stack <- [(tree.root_node, depth=0)]
    while stack is not empty:
        node, depth <- stack.pop()
        counts.n_total_nodes += 1
        counts.max_depth <- max(counts.max_depth, depth)
        if node.type in {for_statement, while_statement, do_statement}: counts.n_loops += 1
        if node.type == if_statement: counts.n_if_statements += 1
        if node.type in {pointer_declarator, pointer_expression}: counts.n_pointer_ops += 1
        ... (assignment/return/call/binary-op/error-node counters, same pattern)
        push each child of node onto stack at depth+1
    return counts
```

This mirrors the real implementation in `app/utils.py::extract_ast_features` (lines 135–~250), which
uses an **explicit stack instead of recursion** specifically because a large C function can produce an
AST several thousand nodes deep, which would exceed Python's default recursion limit (1000) if
implemented as a naive recursive tree walk — a concrete, documented engineering decision rather than an
arbitrary style choice.

### 5.2.2 Flowchart (Feature Fusion → Prediction, described)

Source function → [AST branch: tree-sitter parse → 11 counts] and [Metrics branch: line/text analysis
→ 13 counts] and [Semantic branch: CodeBERT tokenizer + model → 768-d `[CLS]` embedding] running
independently → `build_feature_vector` concatenates the three in the fixed order (AST, metrics,
embedding) into one 792-d vector → the trained XGBoost (or Random Forest) model scores the vector →
`get_verdict` converts the raw probability into a verdict, risk level, and confidence using the
project's chosen decision threshold (0.26, selected via `src/model/threshold_experiment.py` to
maximize F1 on a validation carve-out, never on the test set).

### 5.2.3 Model Training and Fine-Tuning

`src/model/train_classifier.py` trains XGBoost (`n_estimators=100`, `max_depth=6`,
`learning_rate=0.1`, `scale_pos_weight` set from the training split's class ratio) and Random Forest
(`n_estimators=100`, `class_weight="balanced"`) on the 21,784-row training split, evaluates both on the
5,447-row held-out test split, and serializes the winning artifacts to `models/xgboost.json` and
`models/random_forest.joblib` along with `models/training_metadata.json` (the single source of truth
for every metric reported in this document — Chapter 7). CodeBERT itself is **not** fine-tuned; it is
used strictly as a frozen embedding extractor, which keeps the offline training step to tree-ensemble
fitting on a fixed feature table rather than a full deep-learning training run.

### 5.2.4 Code Snippets and Explanation

**Per-function inference, not whole-file truncation** (`backend/ml_bridge.py::run_prediction`). An
important, measured engineering correction: CodeBERT truncates its input at 512 tokens, and the project
measured that scanning an uploaded file as one whole blob silently truncated 80% of real files to
roughly their first 15% of content, versus only 45.5% truncation when each function inside the file is
split out and scored independently (matching the granularity — individual functions — the model was
actually trained on). `run_prediction` therefore splits multi-function input with the same tree-sitter
grammar used elsewhere in the codebase, scores each function independently, and reports the **worst**
function's result as the file-level verdict — an "escalate to the worst signal, never suppress"
principle applied consistently across the codebase (the same rule governs how a disagreeing
deterministic line-scan is allowed to raise, but never lower, the displayed risk level).

```python
def run_prediction(code: str, model_choice: str = "XGBoost") -> dict:
    xgb_model = get_xgb_model()
    rf_model = get_rf_model()
    if model_choice == "XGBoost" and xgb_model is not None:
        active_model, active_name = xgb_model, "XGBoost"
    elif model_choice == "Random Forest" and rf_model is not None:
        active_model, active_name = rf_model, "Random Forest"
    elif xgb_model is not None:
        active_model, active_name = xgb_model, "XGBoost (fallback)"
    elif rf_model is not None:
        active_model, active_name = rf_model, "Random Forest (fallback)"
    else:
        active_model, active_name = None, None

    if active_model is not None:
        tokenizer, codebert_model = get_codebert()
        result = _predict_per_function_or_whole(code, active_model, active_name, tokenizer, codebert_model)
        result["is_demo"] = False
    else:
        result = demo_predict(code)
    ...
```
*(Source: `backend/ml_bridge.py`, lines 89–136.)*

**Safety-checked automated patching** (`backend/routers/patches.py::apply_patch`). The Apply-Patch →
Re-Scan loop always recomputes the rewrite from the scan's own stored source (never trusts a
client-supplied "already fixed" snippet, which would let a tampered request bypass the safety check
below), and refuses to apply a rewrite at all if any part of it used an unknown placeholder buffer
size rather than a statically known one — a deliberate design choice to avoid feeding the model a
syntactically-templated, non-compilable snippet and presenting a misleading before/after comparison:

```python
rewrite = recommendations.suggest_secure_rewrite(record.code)
if not rewrite["changed"]:
    raise HTTPException(status_code=400, detail="No auto-fixable pattern found in this scan.")
if rewrite["requires_manual_sizing"]:
    raise HTTPException(status_code=422, detail={
        "blocked": True,
        "reason": "One or more of the generated fixes use a dest_size PLACEHOLDER, not a real, "
                  "statically-known buffer capacity ...",
    })
```
*(Source: `backend/routers/patches.py`, lines 27–70.)* The successful path creates a **new**
`ScanRecord` (`derived_from_scan_id` pointing at the original) rather than mutating the original scan,
so reverting to the pre-patch state is simply navigating back to the original record.

### 5.3.1 Key Functionalities

- **Deterministic line-risk scanning** — a regex-based scanner independent of the ML model, matching
  known-dangerous API patterns (buffer overflow, format-string, use-after-free, etc.) to produce
  line-level highlighting; used to cross-check, and only ever escalate, the ML verdict.
- **Approximate feature contribution** — an importance × z-score approximation (explicitly documented
  in the code as not true SHAP) used to give an indicative, not authoritative, per-feature explanation
  in the Analysis page.
- **PCA embedding projection** — a 2-D PCA projection of a scanned function's CodeBERT embedding,
  plotted against a background of training-set points, giving a visual sense of where a new function
  falls relative to the training distribution.
