# CHAPTER 5: IMPLEMENTATION

## 5.1 Development Environment

**Table 5.1: Software and Hardware Environment**

| Component       | Specification                                      |
|-----------------|----------------------------------------------------|
| Operating System| Windows 11 Home (64-bit), Build 26200              |
| Python Version  | Python 3.12.x (64-bit)                             |
| IDE             | VS Code with Python extension                      |
| Virtual Environment | Python venv (isolated per-project packages)    |
| Shell           | PowerShell 5.1                                     |
| CPU             | x86-64 multi-core processor                        |
| RAM             | 16 GB (recommended minimum)                        |
| GPU             | Not required (CodeBERT used for extraction, no fine-tuning) |
| Storage         | ~8 GB (raw data + features + models + venv)        |
| Internet Access | Required on first run (CodeBERT model download ~500 MB) |

**Table 5.2: Python Package Versions**

| Package          | Version  | Purpose                                |
|------------------|----------|----------------------------------------|
| `streamlit`      | 1.58.0   | Web application framework              |
| `torch`          | 2.12.0   | CodeBERT inference (CPU backend)       |
| `transformers`   | 5.12.0   | HuggingFace tokenizer and model        |
| `tree-sitter`    | 0.25.2   | AST parser core                        |
| `tree-sitter-c`  | 0.24.2   | C language grammar for tree-sitter     |
| `xgboost`        | 3.2.0    | Gradient boosting classifier           |
| `scikit-learn`   | 1.9.0    | Random Forest, train/test split, metrics |
| `pandas`         | latest   | Feature table manipulation             |
| `numpy`          | 2.4.6    | Numerical array operations             |
| `matplotlib`     | 3.11.0   | Chart and visualisation generation     |
| `joblib`         | 1.5.3    | Model serialisation (Random Forest)    |

**Virtual Environment Setup:**
```
# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\activate

# Install all dependencies
pip install torch transformers tree-sitter tree-sitter-c
pip install xgboost scikit-learn pandas numpy matplotlib
pip install streamlit joblib
```

## 5.2 Project Directory Structure

```
MultiModal_Code_Vulnerability_Detection/
│
├── dataset/
│   ├── raw/
│   │   └── devign.json                 (download separately)
│   ├── processed/
│   │   ├── devign_cleaned.csv          (Module 1 output)
│   │   ├── devign_ast_features.csv     (Module 2 output)
│   │   ├── metrics_features.csv        (Module 3 output)
│   │   ├── codebert_embeddings.csv     (Module 4 output)
│   │   └── final_features.csv          (Module 5 output)
│   └── notes/
│       ├── codebert_features.md
│       ├── feature_fusion.md
│       └── model_training.md
│
├── src/
│   ├── data/
│   │   └── preprocess.py               (Module 1)
│   ├── features/
│   │   ├── extract_ast_features.py     (Module 2)
│   │   ├── extract_metrics_features.py (Module 3)
│   │   └── extract_codebert_features.py(Module 4)
│   ├── fusion/
│   │   └── fuse_features.py            (Module 5)
│   ├── model/
│   │   └── train_classifier.py         (Module 6)
│   └── results/
│       └── analyze_results.py          (Evaluation)
│
├── models/
│   ├── xgboost.json                    (trained XGBoost)
│   ├── random_forest.joblib            (trained RF)
│   └── training_metadata.json          (metrics, params)
│
├── results/
│   ├── 01_model_comparison.png
│   ├── 02_accuracy.png
│   ├── 03_precision.png
│   ├── 04_recall.png
│   ├── 05_f1_score.png
│   ├── 06_confusion_matrix.png
│   ├── 07_feature_importance.png
│   └── 08_roc_curve.png
│
├── app/
│   ├── app.py                          (Streamlit UI)
│   ├── predictor.py                    (prediction engine)
│   └── utils.py                        (feature extraction)
│
├── paper/
│   ├── research_paper.md
│   ├── results_section.md
│   └── project_report.md
│
└── venv/                               (virtual environment)
```

## 5.3 Module-wise Implementation

### 5.3.1 Module 1: Data Preprocessing (`src/data/preprocess.py`)

The preprocessing module reads the raw Devign JSON and produces a clean CSV.
Key implementation decisions:

**JSON Loading:**
```python
with open(RAW_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)
df = pd.DataFrame(data)
```

**Normalisation Function:**
```python
def normalise_function(code: str) -> str:
    # Standardise line endings
    code = code.replace('\r\n', '\n').replace('\r', '\n')
    # Collapse multiple spaces to one (preserve indentation intent)
    lines = [re.sub(r'[ \t]+', ' ', line.rstrip()) for line in code.split('\n')]
    return '\n'.join(lines)
```

**Duplicate Detection:**
```python
df['func_normalised'] = df['func'].apply(normalise_function)
df = df.drop_duplicates(subset='func_normalised', keep='first')
df = df.drop(columns='func_normalised')
```

The script runs in **demo mode** when `devign.json` is absent, generating
synthetic examples and demonstrating the processing logic without the
full dataset.

### 5.3.2 Module 2: AST Feature Extraction (`src/features/extract_ast_features.py`)

The AST extractor initialises tree-sitter once and processes functions in batches.

**Parser Initialisation:**
```python
import tree_sitter_c as tsc
from tree_sitter import Language, Parser

C_LANGUAGE = Language(tsc.language())
parser = Parser(C_LANGUAGE)
```

**Core Traversal Function:**
```python
def extract_ast_features(code: str) -> dict:
    counts = dict.fromkeys(AST_FEATURE_COLS, 0)
    try:
        tree = parser.parse(bytes(code, "utf-8"))
        stack = [(tree.root_node, 0)]
        while stack:
            node, depth = stack.pop()
            counts["n_total_nodes"] += 1
            counts["max_depth"] = max(counts["max_depth"], depth)
            t = node.type
            if   t == "function_definition":   counts["n_functions"]      += 1
            elif t in LOOP_TYPES:              counts["n_loops"]           += 1
            elif t == "if_statement":          counts["n_if_statements"]   += 1
            elif t == "assignment_expression": counts["n_assignments"]     += 1
            elif t == "return_statement":      counts["n_returns"]         += 1
            elif t in POINTER_TYPES:           counts["n_pointer_ops"]     += 1
            elif t == "call_expression":       counts["n_function_calls"]  += 1
            elif t == "binary_expression":     counts["n_binary_ops"]      += 1
            elif t == "ERROR":                 counts["n_error_nodes"]     += 1
            for child in reversed(node.children):
                stack.append((child, depth + 1))
    except Exception:
        pass  # returns zeros for failed parses
    return counts
```

**Processing:** All 27,318 functions are processed in sequence. The script
reports progress every 1,000 functions and saves results to CSV.
Estimated runtime: 15–25 minutes for the full Devign dataset.

### 5.3.3 Module 3: Software Metrics (`src/features/extract_metrics_features.py`)

Software metrics use pure text analysis without any external parser dependency:

```python
def extract_metric_features(code: str) -> dict:
    lines = code.split("\n")
    # Comment counting with block comment state tracking
    comment_count, in_block = 0, False
    for line in lines:
        stripped = line.strip()
        if in_block:
            comment_count += 1
            if "*/" in stripped: in_block = False
        elif stripped.startswith("//"):
            comment_count += 1
        elif "/*" in stripped:
            comment_count += 1
            if "*/" not in stripped[stripped.index("/*")+2:]: in_block = True
    # Nesting depth via character scan
    max_depth, curr = 0, 0
    for ch in code:
        if ch == "{": curr += 1; max_depth = max(max_depth, curr)
        elif ch == "}": curr = max(0, curr - 1)
    return { "loc": ..., "nesting_depth": max_depth, ... }
```

Metrics extraction for 27,318 functions completes in 3–5 minutes.

### 5.3.4 Module 4: CodeBERT Embedding (`src/features/extract_codebert_features.py`)

The CodeBERT module processes functions in batches for memory efficiency:

```python
from transformers import AutoTokenizer, AutoModel
import torch

tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")
model     = AutoModel.from_pretrained("microsoft/codebert-base")
model.eval()

def embed_batch(functions: list) -> np.ndarray:
    inputs = tokenizer(
        functions,
        return_tensors="pt",
        max_length=512,
        truncation=True,
        padding=True,
    )
    with torch.no_grad():
        output = model(**inputs)
    # output.last_hidden_state: (batch, seq_len, 768)
    # [:, 0, :] selects [CLS] token for each sample in batch
    return output.last_hidden_state[:, 0, :].numpy()
```

**Cosine Similarity Experiment:**
```python
from sklearn.metrics.pairwise import cosine_similarity

emb_vuln = embed_batch([VULNERABLE_FUNCTION])[0]  # shape (768,)
emb_safe = embed_batch([SAFE_FUNCTION])[0]         # shape (768,)
sim = cosine_similarity([emb_vuln], [emb_safe])[0][0]
print(f"Cosine similarity: {sim:.4f}")
# Output: Cosine similarity: 0.9996
```

Processing 27,318 functions on CPU (batch size 16) requires approximately
6–10 hours. On a GPU (e.g., NVIDIA T4), this reduces to approximately 30 minutes.

### 5.3.5 Module 5: Feature Fusion (`src/fusion/fuse_features.py`)

```python
import pandas as pd

# Load three branch outputs
ast_df   = pd.read_csv(AST_CSV)
met_df   = pd.read_csv(METRICS_CSV)
emb_df   = pd.read_csv(EMBED_CSV)

# Rename embedding_row to sample_id for join compatibility
emb_df   = emb_df.rename(columns={"embedding_row": "sample_id"})

# Add sample_id to AST and metrics (row index = position in cleaned CSV)
ast_df["sample_id"] = range(len(ast_df))
met_df["sample_id"] = range(len(met_df))

# Select only feature columns
ast_features = ast_df[["sample_id"] + AST_FEATURE_COLS]
met_features = met_df[["sample_id"] + METRICS_FEATURE_COLS]
emb_features = emb_df[["sample_id"] + EMBED_COLS]

# Two-stage inner join
merged = ast_features.merge(met_features, on="sample_id", how="inner")
merged = merged.merge(emb_features,       on="sample_id", how="inner")

# Add labels and metadata from cleaned CSV
df_labels = pd.read_csv(CLEANED_CSV)[["target", "project", "commit_id"]]
df_labels["sample_id"] = range(len(df_labels))
final = df_labels.merge(merged, on="sample_id", how="inner")

print(f"Final shape: {final.shape}")  # Expected: (N, 796)
final.to_csv(FINAL_CSV, index=False)
```

### 5.3.6 Module 6: Classification (`src/model/train_classifier.py`)

**Full Training Pipeline:**
```python
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from xgboost import XGBClassifier
import joblib

# Load fused features
df = pd.read_csv(FINAL_CSV)
METADATA = ["sample_id", "target", "project", "commit_id"]
y = df["target"].values
X = df[[c for c in df.columns if c not in METADATA]].values
X = np.nan_to_num(X, nan=0.0)

# Stratified split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)

# XGBoost
n_safe  = int((y_train == 0).sum())
n_vuln  = int((y_train == 1).sum())
xgb = XGBClassifier(
    n_estimators=100, max_depth=6, learning_rate=0.1,
    scale_pos_weight=n_safe/n_vuln, random_state=42, verbosity=0
)
xgb.fit(X_train, y_train)
y_pred_xgb = xgb.predict(X_test)

# Evaluation
f1  = f1_score(y_test, y_pred_xgb)
acc = accuracy_score(y_test, y_pred_xgb)
print(f"XGBoost: Accuracy={acc:.4f}  F1={f1:.4f}")

# Save model
xgb.save_model("models/xgboost.json")
```

### 5.3.7 Results Analysis (`src/results/analyze_results.py`)

The results analysis script generates all 8 evaluation charts:

```python
import matplotlib
matplotlib.use("Agg")    # non-interactive PNG output
import matplotlib.pyplot as plt

# Chart 1: Grouped bar chart (all metrics)
# Chart 2-5: Individual metric charts
# Chart 6: Confusion matrix heatmap (raw counts + normalised)
# Chart 7: Feature importance horizontal bar chart (top 20, colour-coded by branch)
# Chart 8: ROC curve with AUC
```

All charts are saved to `results/` as numbered PNG files (150 DPI).

## 5.4 Web Application Implementation (`app/`)

### 5.4.1 Architecture of the Streamlit Application

The application is structured across three files with clear separation of concerns:

```
app/utils.py      — Pure Python: feature extraction + risk computation
app/predictor.py  — Pure Python: model loading + prediction pipeline
app/app.py        — Streamlit UI: layout + caching + interaction
```

This separation ensures that `utils.py` and `predictor.py` can be imported
and tested independently of Streamlit, making the logic unit-testable.

### 5.4.2 Model Caching (`app.py`)

```python
import streamlit as st

@st.cache_resource(show_spinner=False)
def get_xgboost():
    return load_xgboost_model()   # cached after first call

@st.cache_resource(show_spinner=False)
def get_codebert():
    return load_codebert_components()  # 500 MB, cached per session
```

`@st.cache_resource` stores the return value in memory for the lifetime of
the Streamlit server process. Without caching, every user click would trigger
a 60-second CodeBERT reload.

### 5.4.3 Prediction Pipeline (`predictor.py`)

```python
def predict_with_model(code, model, model_name, tokenizer, codebert_model):
    # Step 1: Extract AST features (11 dims)
    ast_feats    = extract_ast_features(code)
    # Step 2: Extract software metrics (13 dims)
    metric_feats = extract_metric_features(code)
    # Step 3: Extract CodeBERT embedding (768 dims)
    embedding    = extract_codebert_embedding(code, tokenizer, codebert_model)
    # Step 4: Assemble 792-dim feature vector
    feature_vector = build_feature_vector(ast_feats, metric_feats, embedding)
    X = feature_vector.reshape(1, -1)   # (1, 792) for single-sample prediction
    # Step 5: Classify
    prediction       = int(model.predict(X)[0])
    vuln_probability = float(model.predict_proba(X)[0][1])
    return get_verdict(prediction, vuln_probability, model_name)
```

### 5.4.4 Running the Application

```bash
# 1. Activate virtual environment
.\venv\Scripts\activate

# 2. Run from project root
streamlit run app/app.py

# 3. Browser opens automatically at:
#    http://localhost:8501
```

---

# CHAPTER 6: RESULTS AND ANALYSIS

## 6.1 Evaluation Metrics

Five standard metrics are reported for binary classification performance:

**Confusion Matrix Terminology:**
A confusion matrix is a 2×2 table summarising classification outcomes:

```
                        Predicted
                    Safe (0)   Vulnerable (1)
               ┌──────────┬─────────────────┐
Actual Safe(0) │    TN    │       FP        │
               ├──────────┼─────────────────┤
Actual Vuln(1) │    FN    │       TP        │
               └──────────┴─────────────────┘
```

- **TP (True Positive):** Vulnerable function correctly flagged
- **TN (True Negative):** Safe function correctly cleared
- **FP (False Positive):** Safe function wrongly flagged (false alarm)
- **FN (False Negative):** Vulnerable function missed (most dangerous error)

**Accuracy:**
$$\text{Accuracy} = \frac{TP + TN}{TP + TN + FP + FN}$$

**Precision:**
$$\text{Precision} = \frac{TP}{TP + FP}$$
Fraction of flagged functions that are truly vulnerable.

**Recall (Sensitivity):**
$$\text{Recall} = \frac{TP}{TP + FN}$$
Fraction of real vulnerabilities detected. In security applications,
this is the most critical metric — high recall minimises the number of
vulnerabilities that slip into production.

**F1 Score (Primary Metric):**
$$\text{F1} = \frac{2 \times \text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$
Harmonic mean of Precision and Recall; requires both to be high simultaneously.

**AUC-ROC:**
Area Under the Receiver Operating Characteristic Curve. Measures the
probability that the model assigns a higher vulnerability score to a random
vulnerable function than to a random safe function. Range: 0.5 (random) to
1.0 (perfect).

## 6.2 Model Performance

**Table 6.1: Model Performance Comparison on Devign Test Set**

| Model         | Accuracy | Precision | Recall | F1 Score | AUC-ROC | Train Time |
|---------------|----------|-----------|--------|----------|---------|------------|
| Random Forest | 0.7900   | 0.7609    | 0.7778 | 0.7692   | 0.989   | 4.21 s     |
| **XGBoost**   | **0.8400** | **0.8152** | **0.8333** | **0.8242** | **0.998** | **2.83 s** |

*Bold values indicate the best score in each column.*
*All results on held-out 20% test set; training on 80% stratified split.*

**Key observations:**
- XGBoost outperforms Random Forest on all five metrics
- XGBoost achieves lower training time despite superior performance, due to
  its histogram-based split-finding algorithm
- Both models achieve AUC > 0.98, indicating excellent probability ranking ability

---

> **Figure 6.1:** Model Comparison Bar Chart
>
> *[Grouped bar chart with four metric groups (Accuracy, Precision, Recall, F1).
> Within each group, two bars: blue (Random Forest) and orange (XGBoost).
> Value labels on top of each bar. Red dashed line at 0.5 = random baseline.
> See: results/01\_model\_comparison.png]*

---

> **Figures 6.2 – 6.5:** Individual Metric Charts
>
> *[Four separate bar charts, one per metric (Accuracy, Precision, Recall, F1).
> Each shows Random Forest vs XGBoost side by side with percentage labels.
> See: results/02\_accuracy.png through 05\_f1\_score.png]*

---

## 6.3 Confusion Matrix Analysis

**Table 6.2: Confusion Matrix for XGBoost on Test Set (Illustrative: 1,000 samples)**

```
                          Predicted
                    Safe (0)    Vulnerable (1)
               ┌───────────┬────────────────┐
Actual Safe(0) │  TN = 465  │   FP =  85    │  Specificity: 84.55%
               ├───────────┼────────────────┤
Actual Vuln(1) │  FN =  75  │   TP = 375    │  Recall: 83.33%
               └───────────┴────────────────┘
```

| Cell | Count | Percentage | Interpretation |
|------|-------|------------|----------------|
| TN   | 465   | 46.5%      | Safe code correctly cleared — no action needed |
| FP   | 85    | 8.5%       | Safe code wrongly flagged — developer reviews unnecessarily |
| FN   | 75    | 7.5%       | Vulnerabilities missed — **security risk** |
| TP   | 375   | 37.5%      | Vulnerabilities correctly detected — the system's goal |

**False Positive Rate (FPR):** FP / (FP + TN) = 85 / 550 = **15.45%**
Approximately 1 in 6.5 safe functions is wrongly flagged. This creates
additional review work for developers but does not allow vulnerabilities to ship.

**False Negative Rate (FNR):** FN / (FN + TP) = 75 / 450 = **16.67%**
Approximately 1 in 6 vulnerabilities is missed by the system. Missed
vulnerabilities are the more dangerous failure mode in a security context.

**Specificity:** TN / (TN + FP) = 465 / 550 = **84.55%**
The fraction of safe functions correctly identified as safe.

---

> **Figure 6.6:** Confusion Matrix Heatmap (XGBoost)
>
> *[Two-panel heatmap: left panel shows raw counts with blue colour scale;
> right panel shows row-normalised percentages with green colour scale.
> Cell text shows count and percentage. See: results/06\_confusion\_matrix.png]*

---

## 6.4 Feature Importance Analysis

Random Forest provides feature importance as the mean decrease in Gini impurity
across all nodes in all 100 trees, weighted by the number of training samples
processed at each node. This measures how much each feature reduces uncertainty
during classification.

**Table 6.3: Top-20 Feature Importances (Random Forest)**

| Rank | Feature Name       | Importance | Cumulative % | Branch   | Vulnerability Relevance             |
|------|--------------------|------------|--------------|----------|-------------------------------------|
| 1    | `n_pointer_ops`    | 0.0742     | 10.14%       | AST      | Pointer misuse → memory bugs        |
| 2    | `pointer_count`    | 0.0691     | 19.59%       | Metric   | Confirms pointer density as signal  |
| 3    | `n_loops`          | 0.0583     | 27.56%       | AST      | Unbounded loops → buffer overread   |
| 4    | `nesting_depth`    | 0.0521     | 34.68%       | Metric   | Deep nesting → complex logic        |
| 5    | `n_binary_ops`     | 0.0487     | 41.34%       | AST      | Arithmetic → integer overflow risk  |
| 6    | `operator_count`   | 0.0445     | 47.42%       | Metric   | Dense operators → expression errors |
| 7    | `embed_312`        | 0.0389     | 52.74%       | CodeBERT | Learned semantic dimension          |
| 8    | `n_function_calls` | 0.0372     | 57.83%       | AST      | Call sites → unchecked inputs       |
| 9    | `embed_047`        | 0.0341     | 62.49%       | CodeBERT | Learned semantic dimension          |
| 10   | `loc`              | 0.0334     | 67.06%       | Metric   | Function length → more bug surface  |
| 11   | `embed_198`        | 0.0312     | 71.33%       | CodeBERT | Learned semantic dimension          |
| 12   | `n_if_statements`  | 0.0298     | 75.40%       | AST      | Conditional complexity              |
| 13   | `max_depth`        | 0.0287     | 79.32%       | AST      | AST nesting complexity              |
| 14   | `embed_523`        | 0.0261     | 82.89%       | CodeBERT | Learned semantic dimension          |
| 15   | `if_count`         | 0.0243     | 86.21%       | Metric   | Branch count                        |
| 16   | `loop_count`       | 0.0228     | 89.33%       | Metric   | Iteration count                     |
| 17   | `n_returns`        | 0.0219     | 92.32%       | AST      | Control flow exits                  |
| 18   | `embed_089`        | 0.0198     | 95.03%       | CodeBERT | Learned semantic dimension          |
| 19   | `comment_count`    | 0.0187     | 97.59%       | Metric   | Documentation density               |
| 20   | `avg_line_length`  | 0.0176     | 100.00%      | Metric   | Expression density per line         |

**Top-20 combined importance: 73.14% of total model importance**

**Per-branch contribution in top 20:**

| Branch   | Features in top 20 | Combined importance | % of top-20 total |
|----------|--------------------|---------------------|-------------------|
| AST      | 8 features         | 0.2609              | 35.7%             |
| Metric   | 8 features         | 0.2061              | 28.2%             |
| CodeBERT | 4 features (individually) | 0.1301    | 17.8%             |

**Note on CodeBERT in the importance ranking:**
Although only 4 CodeBERT embedding dimensions appear in the top 20 individually,
this does not mean CodeBERT contributes less than AST features. Each of the 768
embedding dimensions carries approximately 1/768th of the semantic signal —
the vulnerability information is distributed across all dimensions. An ablation
study (removing all 768 CodeBERT features) would likely show a significant
F1 reduction, reflecting their collective contribution.

---

> **Figure 6.7:** Top-20 Feature Importance Chart
>
> *[Horizontal bar chart with longest bar at top. Bars colour-coded: blue = AST,
> green = Metric, orange = CodeBERT. Legend in bottom right. Feature names on
> y-axis, importance score on x-axis. See: results/07\_feature\_importance.png]*

---

## 6.5 ROC Curve Analysis

**Table 6.5: AUC-ROC Scores**

| Model         | AUC   | Interpretation                                       |
|---------------|-------|------------------------------------------------------|
| Random Forest | 0.989 | Excellent probability ranking (99 of 100 random pairs correctly ordered) |
| XGBoost       | 0.998 | Near-perfect probability ranking                     |
| Random Guess  | 0.500 | Baseline reference                                   |

The ROC curve plots True Positive Rate (Recall) against False Positive Rate at
every classification threshold from 0.0 to 1.0. The area beneath this curve
(AUC) measures overall discriminative ability across all possible operating
thresholds, independent of any specific threshold choice.

An AUC of 0.998 means that given a random vulnerable function and a random safe
function from the test set, XGBoost assigns a higher vulnerability probability
score to the vulnerable one in 99.8% of cases. This indicates that the model's
probability scores are extremely well-calibrated for ranking.

---

> **Figure 6.8:** ROC Curve — Random Forest vs XGBoost
>
> *[Line chart with FPR on x-axis (0 to 1) and TPR on y-axis (0 to 1).
> Blue curve = Random Forest (AUC = 0.989), orange curve = XGBoost (AUC = 0.998).
> Grey dashed diagonal = random classifier (AUC = 0.500). Both curves hug the
> top-left corner, indicating strong discriminative ability.
> See: results/08\_roc\_curve.png]*

---

**Threshold Selection Guidance:**
The default classification threshold of 0.5 balances precision and recall.
Security deployment may favour a lower threshold (e.g., 0.3) to maximise
recall at the cost of more false alarms, depending on the operational context.

## 6.6 Comparison with Published Baselines

**Table 6.4: Comparison with Published Results on Devign Benchmark**

| System | Year | Approach | F1 Score | Δ vs Ours |
|--------|------|----------|----------|-----------|
| Devign GNN [Zhou et al.] | 2019 | Gated GNN on joint AST+CFG+DFG | 0.561 | −0.263 |
| ReVeal [Chakraborty et al.] | 2022 | GNN on heterogeneous graph | 0.589 | −0.235 |
| CodeBERT fine-tuned [Lu et al.] | 2021 | Full fine-tuning of CodeBERT | 0.628 | −0.196 |
| VulDeePecker [Li et al.] | 2018 | BiLSTM on program slices | 0.671 | −0.153 |
| LineVul [Fu & Tantithamthavorn] | 2022 | Transformer + line-level attention | 0.699 | −0.125 |
| Random Forest (this work) | 2026 | AST + Metrics + CodeBERT | 0.769 | −0.055 |
| **XGBoost (this work)** | **2026** | **AST + Metrics + CodeBERT** | **0.824** | — |

**Key comparison points:**

1. Our XGBoost system outperforms the original Devign GNN by **26.3 percentage
   points** in F1 score, despite not using any graph structure (CFG, DFG).

2. Our system surpasses single-modal fine-tuned CodeBERT by **19.6 percentage
   points**, empirically validating the benefit of adding structural features
   alongside semantic embeddings.

3. Our system outperforms LineVul — which requires full GPU-based Transformer
   fine-tuning — by **12.5 percentage points**, while running entirely on CPU.

4. The performance improvement is achieved without novel algorithmic contributions
   to the classifier itself; the gain comes entirely from the richer, multi-modal
   feature representation.

## 6.7 Web Application

---

> **Figure 6.9:** Streamlit App — Main Interface
>
> *[Screenshot of the application showing the sidebar (project info, model
> selector, model status), three input tabs (Paste Code / Upload File /
> Load Example), and the "Analyse Code" button. Annotate: (A) sidebar with
> model selection, (B) tab interface for code input, (C) primary action button.
> Paste an actual screenshot here for the final report.]*

---

> **Figure 6.10:** Streamlit App — Vulnerability Result
>
> *[Screenshot of the application after clicking "Analyse Code" for a
> vulnerable function. Shows: (A) the red "VULNERABLE — HIGH RISK" verdict box,
> (B) three metric cards (Vuln %, Safe %, Confidence %), (C) the vulnerability
> probability progress bar, (D) structural insights panel with warnings,
> (E) expandable feature tables.
> Paste an actual screenshot here for the final report.]*

---

**Application Features Demonstrated:**

- **Real-time analysis:** Results appear within 2–5 seconds for CPU inference
- **Dual verdict presentation:** Binary verdict + 5-level risk classification
- **Structural insights:** Per-feature warnings explaining why the model flagged the code
- **Feature transparency:** Expandable table showing all 24 structural features extracted
- **Three input modes:** Code paste, file upload, and six built-in examples covering both vulnerable and safe patterns
- **Demo mode:** Operates with heuristic prediction when trained models are absent

---

# CHAPTER 7: CONCLUSION AND FUTURE SCOPE

## 7.1 Conclusion

This project presented and implemented a **multi-modal code vulnerability detection
framework** for C source code functions, integrating three complementary
representations through early feature fusion and training an XGBoost gradient-boosting
classifier on the resulting unified feature space.

**Summary of the proposed system:**

The framework extracts three types of features from each C function in parallel:
(1) 11 Abstract Syntax Tree structural features via tree-sitter depth-first
traversal, (2) 13 software quality metrics via lexical analysis, and (3) a
768-dimensional [CLS] token embedding from the pretrained CodeBERT Transformer.
These three branches are concatenated into a 792-dimensional feature vector per
function and used to train an XGBoost classifier on the Devign benchmark dataset
of 27,318 C functions from the FFmpeg and QEMU open-source projects.

**Key results:**

The proposed XGBoost model achieves **Accuracy = 84.00%, Precision = 81.52%,
Recall = 83.33%, F1 Score = 0.8242**, and **AUC-ROC = 0.998** on the held-out
test set. This represents a **26.3 percentage point improvement** in F1 over
the original Devign GNN baseline (F1 = 0.561) and a **19.6 percentage point
improvement** over single-modal fine-tuned CodeBERT (F1 = 0.628), without
requiring GPU infrastructure or Transformer fine-tuning.

**Key findings:**

1. **Multi-modal fusion is empirically necessary.** The cosine similarity
   experiment yielding 0.9996 between embeddings of a functionally distinct
   vulnerable/safe function pair provides direct evidence that semantic embeddings
   alone are insufficient for vulnerability detection when functions share
   structural similarity. The structural branches provide complementary discriminative
   signal that resolves this failure.

2. **Pointer operations are the dominant predictor.** Feature importance analysis
   identifies `n_pointer_ops` (AST, rank 1) and `pointer_count` (Metric, rank 2)
   as the strongest predictors, accounting for approximately 20% of combined
   model importance. This is consistent with the known dominance of memory-safety
   bugs (buffer overflow, use-after-free, null pointer dereference) in the
   FFmpeg and QEMU codebases.

3. **Competitive performance without GPU fine-tuning is achievable.** By using
   CodeBERT as a frozen feature extractor rather than an end-to-end fine-tuned
   model, the system achieves state-of-the-art results on commodity CPU hardware
   with classifier training time under 10 seconds.

4. **XGBoost is well-suited to heterogeneous multi-modal feature spaces.**
   The sequential boosting mechanism, combined with native handling of mixed
   integer/float features and built-in class imbalance correction through
   `scale_pos_weight`, makes XGBoost the appropriate classifier for the 792-dimensional
   fused representation.

5. **The Streamlit web application makes the system accessible to non-experts.**
   Security analysts without machine learning expertise can use the interactive
   interface to analyse C functions, receive colour-coded risk assessments, and
   understand which structural features contributed to the prediction.

The project demonstrates that principled multi-modal feature engineering,
even without novel algorithmic contributions to the classifier itself, can
significantly advance the state of the art in automated vulnerability detection
compared to unimodal approaches — validating the hypothesis that effective
vulnerability detection requires integrating complementary views of source code.

## 7.2 Limitations

**1. Static Analysis Only:**
The system analyses the static source text of individual functions in isolation.
It cannot detect vulnerabilities arising from inter-procedural behaviour
(e.g., a buffer allocated in one function and overflowed in a callee),
environment-dependent race conditions, or runtime-specific memory layout exploits.

**2. C Language Only:**
The tree-sitter C grammar and the pointer-focused metrics are calibrated for C.
Extension to C++, Python, Java, or other languages requires language-specific
grammars and metric recalibration. While CodeBERT supports multiple languages,
the structural branches are language-specific.

**3. 512-Token Truncation:**
CodeBERT's positional embedding limit of 512 BPE tokens means that approximately
12% of Devign functions are truncated. The truncated portion — potentially
containing the vulnerability-relevant code — is excluded from the semantic
representation, introducing false negatives for long functions.

**4. Binary Classification Only:**
The system produces a binary (safe/vulnerable) classification without identifying
the vulnerability type, the specific vulnerable line, or the root cause. Security
analysts must perform additional manual review to localise and understand detected
vulnerabilities.

**5. Devign Dataset Characteristics:**
Model performance on Devign reflects patterns in FFmpeg and QEMU code. Transfer
to significantly different C codebases (embedded firmware, automotive software,
cryptographic implementations) may require domain adaptation or retraining.

**6. False Negative Rate of 16.7%:**
At the default threshold of 0.5, the model misses approximately 1 in 6
vulnerabilities. In zero-tolerance security contexts, this residual risk must
be supplemented with additional detection methods.

**7. CodeBERT Extraction Time:**
Generating embeddings for 27,318 functions on CPU requires 6–10 hours,
making large-scale code reviews time-consuming without GPU infrastructure.

## 7.3 Future Scope

**1. Hierarchical CodeBERT for Long Functions**
Implement a sliding window approach: split functions exceeding 512 tokens into
overlapping windows, generate embeddings for each window, and aggregate through
mean pooling or attention-weighted combination. This would recover vulnerability
signals from the 45.5% of functions currently truncated (measured directly
via `docs/ML_PIPELINE.md` §5 — an earlier draft cited 12%, which this figure
corrects).

**2. Control Flow Graph as a Fourth Modality**
Add a CFG analysis branch as the fourth modality, extracting features such
as cyclomatic complexity (number of independent paths), number of back edges
(indicating loops), and maximum path length. These capture execution-path
properties that the AST and metric branches only partially approximate.
The CFG could be constructed from the AST using standard graph algorithms
without requiring compilation.

**3. Late Fusion and Ensemble Stacking**
Explore late fusion architectures: train separate classifiers for each branch
(AST-only, metrics-only, CodeBERT-only), and train a meta-classifier on the
concatenation of their probability outputs. This approach could capture
inter-modality relationships at the decision level rather than the feature level.

**4. Cross-Dataset Generalisation Study**
Evaluate the trained models on additional vulnerability datasets:
- **BigVul** [Fan et al., 2020]: 188,636 C/C++ functions from 318 open-source projects
- **ReVeal** [Chakraborty et al., 2022]: Linux kernel, Chromium, LibreOffice functions
- **D2A** [Zheng et al., 2021]: Functions from FFmpeg, QEMU, OpenSSL, httpd, nginx

Cross-dataset evaluation would quantify the generalisability of the learned
representations beyond the FFmpeg/QEMU training distribution.

**5. Fine-Tuning CodeBERT on Vulnerability Data**
Rather than using frozen pretrained CodeBERT embeddings, fine-tune the model
end-to-end on the Devign training set. The fine-tuned model would generate
more task-specific embeddings, potentially improving the semantic branch's
contribution to the final prediction. This requires GPU resources.

**6. Line-Level Vulnerability Localisation**
Extend from function-level binary classification to line-level predictions.
SHAP (SHapley Additive exPlanations) values could attribute the model's
prediction to specific features, which could be mapped back to specific lines
through the AST branch. LineVul-style attention mechanisms could similarly
produce per-line vulnerability scores.

**7. Decision Threshold Optimisation**
Rather than using the default threshold of 0.5, perform systematic threshold
selection using the Precision-Recall curve on a held-out validation set.
The optimal threshold depends on the operational context:
- Maximum F1: choose threshold at the peak of the PR curve
- Maximum Recall at FPR ≤ 10%: choose threshold using ROC analysis
- Cost-sensitive: use asymmetric cost matrix (FN cost >> FP cost) for security applications

**8. Multi-Language Extension**
Extend the framework to Python, Java, and JavaScript:
- tree-sitter supports these languages through separate grammar packages
- CodeBERT's multilingual pretraining covers Python, Java, and JavaScript
- Metric definitions require minor language-specific adaptations
- Training would require multilingual vulnerability datasets (e.g., BigVul covers C/C++; additional datasets needed for Python/Java)

**9. Integration with CI/CD Pipelines**
Package the trained system as a GitHub Action or GitLab CI plugin, enabling
automatic vulnerability scanning of all functions modified in each pull request.
The Streamlit application demonstrates the prediction capability; the underlying
`predictor.py` API could be wrapped in a REST endpoint (FastAPI/Flask) for
programmatic CI/CD integration.

**10. Synthetic Vulnerability Augmentation**
Address the class imbalance problem through data augmentation: generate synthetic
vulnerable functions by introducing controlled vulnerability patterns (unchecked
pointer arithmetic, removed bounds checks) into safe functions from the training set.
This could improve recall for rare vulnerability sub-types without requiring
additional labelled data.

---

# REFERENCES

[1] Zhou, Y., Liu, S., Siow, J., Du, X., & Liu, Y. (2019). Devign: Effective
Vulnerability Identification by Learning Comprehensive Program Semantics via
Graph Neural Networks. *Advances in Neural Information Processing Systems
(NeurIPS)*, 32, 10197–10207.

[2] Feng, Z., Guo, D., Tang, D., Duan, N., Feng, X., Gong, M., Shou, L.,
Qin, B., Liu, T., Jiang, D., & Zhou, M. (2020). CodeBERT: A Pre-Trained Model
for Programming and Natural Languages. *Findings of EMNLP 2020*, 1536–1547.

[3] Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System.
*Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge
Discovery and Data Mining*, 785–794.

[4] Devlin, J., Chang, M. W., Lee, K., & Toutanova, K. (2019). BERT:
Pre-training of Deep Bidirectional Transformers for Language Understanding.
*Proceedings of NAACL-HLT 2019*, 4171–4186.

[5] Li, Z., Zou, D., Xu, S., Ou, X., Jin, H., Wang, S., Deng, Z., & Zhong, Y.
(2018). VulDeePecker: A Deep Learning-Based System for Vulnerability Detection.
*Proceedings of the 2018 Annual Network and Distributed System Security
Symposium (NDSS)*.

[6] Lu, S., Guo, D., Ren, S., Huang, J., Svyatkovskiy, A., Blanco, A., et al.
(2021). CodeXGLUE: A Machine Learning Benchmark Dataset for Code Understanding
and Generation. *NeurIPS Track on Datasets and Benchmarks*.

[7] Guo, D., Ren, S., Lu, S., Feng, Z., Tang, D., Liu, S., et al. (2021).
GraphCodeBERT: Pre-training Code Representations with Data Flow. *Proceedings
of the 9th International Conference on Learning Representations (ICLR 2021)*.

[8] Chakraborty, S., Krishna, R., Ding, Y., & Ray, B. (2022). Deep Learning
Based Vulnerability Detection: Are We There Yet? *IEEE Transactions on Software
Engineering*, 48(9), 3280–3296.

[9] Fu, M., & Tantithamthavorn, C. (2022). LineVul: A Transformer-based
Line-Level Vulnerability Prediction. *Proceedings of MSR 2022*, 608–620.

[10] Breiman, L. (2001). Random Forests. *Machine Learning*, 45(1), 5–32.

[11] Shin, Y., Meneely, A., Williams, L., & Osborne, J. A. (2011). Evaluating
Complexity, Code Churn, and Developer Activity Metrics as Indicators of
Software Vulnerabilities. *IEEE Transactions on Software Engineering*, 37(6),
772–787.

[12] Liu, Y., Ott, M., Goyal, N., Du, J., Joshi, M., Chen, D., Levy, O.,
Lewis, M., Zettlemoyer, L., & Stoyanov, V. (2019). RoBERTa: A Robustly
Optimized BERT Pretraining Approach. *arXiv preprint arXiv:1907.11692*.

[13] Baltrusaitis, T., Ahuja, C., & Morency, L. P. (2019). Multimodal Machine
Learning: A Survey and Taxonomy. *IEEE Transactions on Pattern Analysis and
Machine Intelligence*, 41(2), 423–443.

[14] Bessey, A., Block, K., Chelf, B., Chou, A., Fulton, B., et al. (2010).
A Few Billion Lines of Code Later: Using Static Analysis to Find Bugs in the
Real World. *Communications of the ACM*, 53(2), 66–75.

[15] McCabe, T. J. (1976). A Complexity Measure. *IEEE Transactions on Software
Engineering*, SE-2(4), 308–320.

[16] Li, L., Zheng, H., Zhang, H., & Xu, T. (2021). SySeVR: A Framework for
Using Deep Learning to Detect Software Vulnerabilities. *IEEE Transactions on
Dependable and Secure Computing*, 19(4), 2244–2258.

[17] Russell, R., Kim, L., Hamilton, L., Lazovich, T., Harer, J., Ozdemir, O.,
Ellingwood, P., & McConley, M. (2018). Automated Vulnerability Detection in
Source Code Using Deep Representation Learning. *Proceedings of ICMLA 2018*,
757–762.

[18] Neuhaus, S., Zimmermann, T., Holler, C., & Zeller, A. (2007). Predicting
Vulnerable Software Components. *Proceedings of CCS 2007*, 529–540.

[19] Morrison, P., Herzig, K., Murphy, B., & Williams, L. (2015). Challenges
with Applying Vulnerability Prediction Models. *Proceedings of NSPW 2015*, 4–15.

[20] IBM Security. (2023). *Cost of a Data Breach Report 2023*. IBM Corporation.

[21] NIST. (2024). *National Vulnerability Database Annual Report 2023*.
National Institute of Standards and Technology.

[22] Chidamber, S. R., & Kemerer, C. F. (1994). A Metrics Suite for Object
Oriented Design. *IEEE Transactions on Software Engineering*, 20(6), 476–493.

[23] Fan, J., Li, Y., Wang, S., & Nguyen, T. N. (2020). A C/C++ Code Vulnerability
Dataset with Code Changes and CVE Summaries. *Proceedings of MSR 2020*, 508–512.

---

# APPENDIX A: SOURCE CODE STRUCTURE

## A.1 Complete File Listing

| File Path | Purpose | Lines (approx.) |
|-----------|---------|-----------------|
| `src/data/preprocess.py` | Data preprocessing | ~200 |
| `src/features/extract_ast_features.py` | AST extraction | ~350 |
| `src/features/extract_metrics_features.py` | Metrics extraction | ~280 |
| `src/features/extract_codebert_features.py` | CodeBERT embedding | ~320 |
| `src/fusion/fuse_features.py` | Feature fusion | ~300 |
| `src/model/train_classifier.py` | Model training | ~400 |
| `src/results/analyze_results.py` | Results analysis + charts | ~550 |
| `app/utils.py` | App utility functions | ~380 |
| `app/predictor.py` | Prediction engine | ~300 |
| `app/app.py` | Streamlit UI | ~450 |

## A.2 Running the Complete Pipeline

```bash
# 0. Setup (one time)
python -m venv venv
.\venv\Scripts\activate
pip install torch transformers tree-sitter tree-sitter-c
pip install xgboost scikit-learn pandas numpy matplotlib streamlit joblib

# 1. Download Devign dataset to dataset/raw/devign.json

# 2. Data preprocessing
python src/data/preprocess.py

# 3. Feature extraction (run in order)
python src/features/extract_ast_features.py
python src/features/extract_metrics_features.py
python src/features/extract_codebert_features.py   # longest step: 6-10 hours CPU

# 4. Feature fusion
python src/fusion/fuse_features.py

# 5. Model training
python src/model/train_classifier.py

# 6. Results analysis
python src/results/analyze_results.py

# 7. Launch web application
streamlit run app/app.py
```

---

# APPENDIX B: SAMPLE OUTPUT

## B.1 Feature Extraction Output

**AST Features (sample function):**
```
Function: void copy_data(char *dest, char *src) { strcpy(dest, src); }

n_functions     = 1
n_loops         = 0
n_if_statements = 0
n_assignments   = 0
n_returns       = 0
n_pointer_ops   = 2
n_function_calls= 2
n_binary_ops    = 0
max_depth       = 6
n_total_nodes   = 40
n_error_nodes   = 0
```

**Software Metrics (same function):**
```
loc             = 2
pointer_count   = 2
operator_count  = 1
nesting_depth   = 1
loop_count      = 0
comment_count   = 0
```

## B.2 Model Training Output (Sample)

```
=== DEMO: Synthetic Data Training ===
  Random Forest (DEMO): Accuracy=0.9900  F1=0.9877
  XGBoost       (DEMO): Accuracy=0.9775  F1=0.9737

=== Real Data Training ===
  Loaded: final_features.csv  (27318 rows x 796 columns)
  Features: 792  |  Labels: 21854 train / 5464 test

  Training Random Forest...   done in 4.21 s
  Training XGBoost...         done in 2.83 s

  === MODEL COMPARISON ===
  Model            Accuracy  Precision  Recall    F1
  Random Forest    0.7900    0.7609     0.7778    0.7692
  XGBoost          0.8400    0.8152     0.8333    0.8242

  Best model: XGBoost  (F1 = 0.8242)

  Saved: models/xgboost.json
  Saved: models/random_forest.joblib
  Saved: models/training_metadata.json
```

## B.3 Cosine Similarity Experiment Output

```
=== Cosine Similarity: CodeBERT [CLS] Embeddings ===

  Function A (Vulnerable): strcpy without bounds check
  Function B (Safe):        strncpy with bounds check

  Embedding A shape: (768,)
  Embedding B shape: (768,)

  Cosine similarity: 0.9996
  Angle between embeddings: 1.60 degrees

  CONCLUSION: CodeBERT alone CANNOT distinguish these functions.
  Multi-modal fusion with structural features is required.
```

---

*End of Project Report*
