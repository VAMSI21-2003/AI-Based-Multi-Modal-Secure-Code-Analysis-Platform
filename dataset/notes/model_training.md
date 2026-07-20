# Model Training — Reference Document
**Project:** Multi-Modal Code Vulnerability Detection Using CodeBERT
**Day:** 9 — Classifier Training and Evaluation
**Script:** src/model/train_classifier.py

---

## Part 1: What is a Classifier?

### The Core Task

A **classifier** is a machine learning model that reads a set of INPUT
NUMBERS and outputs a CATEGORY LABEL.

In our project:

```
INPUT  :  792 numbers per C function
          (11 AST features + 13 metrics + 768 CodeBERT embedding)

OUTPUT :  0  (Non-Vulnerable — the code appears safe)
       OR 1  (Vulnerable — the code contains a likely security flaw)
```

The classifier LEARNS from labelled examples during training:
- "This function represented by [0.12, -0.43, 2.0, ...] was label=1 (vulnerable)"
- "This function represented by [0.05, -0.11, 1.8, ...] was label=0 (safe)"
- Repeated for thousands of examples...

After training, given a NEW C function it has never seen before, the classifier
produces a prediction based on patterns learned from the training examples.

---

## Part 2: The Building Block — Decision Trees

Both Random Forest and XGBoost are built from **Decision Trees**.

### How a Decision Tree Works

A decision tree asks a series of YES/NO questions about the input features:

```
"Is n_loops > 3?"
        |
   YES ─┤
        |── "Is pointer_count > 5?"
        |           |
        |      YES ─┤── PREDICT: VULNERABLE  (label=1)
        |           |
        |      NO  ─┤── "Is nesting_depth > 4?"
        |                       |
        |                  YES ─┤── PREDICT: VULNERABLE
        |                  NO  ─┤── PREDICT: SAFE
   NO  ─┤
        |── "Is loc > 100?"
                    |
               YES ─┤── "Is comment_count < 2?"
                    |               |
                    |          YES ─┤── PREDICT: VULNERABLE
                    |          NO  ─┤── PREDICT: SAFE
               NO  ─┤── PREDICT: SAFE  (label=0)
```

Each YES/NO question is called a **split**. The model learns:
- WHICH feature to ask about at each node (e.g., n_loops vs pointer_count)
- WHAT THRESHOLD to use (e.g., `> 3` vs `> 5`)

The best split is the one that most cleanly separates vulnerable from safe functions.

### How a Tree Learns

The tree scans all possible features and all possible thresholds, and picks the
combination that creates the purest groups after splitting. Purity is measured
by **Gini Impurity** or **Entropy** — concepts from information theory:

- A group is **pure** if it contains ONLY label=0 or ONLY label=1
- A group is **impure** if it mixes 0s and 1s
- A good split creates two groups that are more pure than the parent

### Limitation of a Single Tree

One decision tree is fast and interpretable but has two problems:
1. **Overfitting**: it memorises the training data rather than learning general patterns
2. **High variance**: small changes in training data produce completely different trees

Both Random Forest and XGBoost solve this by combining MANY trees.

---

## Part 3: Random Forest

### The Idea — Wisdom of the Crowd

Random Forest trains **N independent decision trees** (default: 100) and
combines their predictions by **majority vote**.

If 67 trees say "VULNERABLE" and 33 say "SAFE", the final prediction is "VULNERABLE".

```
Training data (3,200 samples)
        |
        +-- Tree 1 (random 80% of samples, random subset of features)
        +-- Tree 2 (different random 80%, different random features)
        +-- Tree 3 (different random 80%, different random features)
        ...
        +-- Tree 100
        
New sample arrives:
        Tree 1 → VULNERABLE (1)
        Tree 2 → VULNERABLE (1)
        Tree 3 → SAFE       (0)
        ...
        Tree 100 → VULNERABLE (1)
        
        Count: 73 trees say 1, 27 trees say 0
        
FINAL PREDICTION → VULNERABLE (1)  (majority vote)
```

### Why Two Levels of Randomness?

**Level 1 — Bootstrap Sampling:**
Each tree sees a RANDOM 80% of the training data (with replacement).
This means each tree is trained on slightly different examples,
making each tree DIVERSE (they disagree and make different mistakes).

**Level 2 — Random Feature Selection:**
At each split inside a tree, only `sqrt(n_features)` randomly chosen features
are considered. For 792 features: `sqrt(792) ≈ 28` features per split.
This prevents any one dominant feature from controlling all trees.

### Why Diversity Matters

- Each tree makes DIFFERENT mistakes (because it saw different data and features)
- When you take the majority vote, individual mistakes CANCEL OUT
- The correct signal ACCUMULATES across all trees
- The ensemble is more robust than any single tree

This is called the **Ensemble Effect** and is the core principle of Random Forest.

### Key Parameters

| Parameter | What it controls | Our setting |
|---|---|---|
| `n_estimators` | Number of trees | 100 |
| `max_features` | Features tested per split | `"sqrt"` (≈28 of 792) |
| `class_weight` | Weight per class | `"balanced"` |
| `random_state` | Reproducibility seed | 42 |
| `n_jobs` | CPU cores to use | -1 (all cores) |

---

## Part 4: XGBoost

### The Idea — Learning from Mistakes

XGBoost (eXtreme Gradient BOOSTing) trains trees **SEQUENTIALLY** instead of
independently. Each new tree specifically corrects the errors of all
previous trees.

```
Start: predict the average label for all samples

Tree 1: learns to reduce the RESIDUALS (errors) of the starting prediction
Tree 2: learns to reduce the remaining errors after Tree 1
Tree 3: learns to reduce the remaining errors after Tree 1 + Tree 2
...
Tree 100: each tree is a small incremental improvement

FINAL PREDICTION = weighted sum of all 100 trees
```

### How It Differs from Random Forest

| Aspect | Random Forest | XGBoost |
|---|---|---|
| Training order | All trees in parallel | One tree at a time (sequential) |
| Each tree's goal | Classify accurately | Reduce the PREVIOUS tree's errors |
| Speed | Fast (parallel) | Usually faster overall (fewer trees needed) |
| Accuracy | Good | Often slightly better |
| Tuning required | Low | More parameters to tune |
| Overfitting risk | Lower | Higher (needs careful learning rate) |

### The Gradient Descent Analogy

"Gradient" in XGBoost refers to the **gradient of the loss function** —
a measure of how wrong the current predictions are. Each new tree is
built in the direction that REDUCES this loss fastest. This is exactly
like gradient descent in neural networks, but applied to decision trees.

### Key Parameters

| Parameter | What it controls | Our setting |
|---|---|---|
| `n_estimators` | Number of trees (rounds) | 100 |
| `max_depth` | Max depth per tree | 6 |
| `learning_rate` | Contribution of each tree | 0.1 |
| `scale_pos_weight` | Class imbalance correction | safe/vuln ratio |
| `verbosity` | Output level | 0 (silent) |

### The Learning Rate

Each tree contributes `learning_rate × tree_prediction` to the final answer.

- Low learning rate (0.01): takes small steps, needs more trees, but rarely overshoots
- High learning rate (0.3): takes large steps, learns faster, but may overshoot

Our setting of 0.1 is the standard default: safe and effective.

---

## Part 5: Why These Models for Our Data?

### The Data Type Problem

Our 792-feature matrix has a **mixed data type problem**:

| Features | Type | Range |
|---|---|---|
| AST features (11) | Integers | 0 to ~200 |
| Metric features (13) | Integers and floats | 0 to ~500 |
| CodeBERT embeddings (768) | Floats | approximately -3 to +14 |

Linear models (like Logistic Regression) struggle with:
- Different scales across features
- Non-linear relationships between features and labels
- High-dimensional inputs (792 features)

### Why Tree-Based Models Are Ideal

Tree models make decisions based on THRESHOLDS, not distances.

A tree asking `"Is n_loops > 3?"` works the same regardless of whether
`loc` has values in range 0-50 or 0-5000. The absolute scale does not matter
— only the ORDER of values within that feature. Therefore:

1. **No normalisation needed**: Trees work with raw feature values
2. **Non-linearity is free**: Trees naturally learn complex non-linear boundaries
3. **Mixed types are fine**: Integer and float features are treated identically
4. **Feature interactions**: Trees learn `"high n_loops AND high pointer_count"` patterns
5. **Robust to outliers**: A single extreme value only affects ONE split threshold
6. **Interpretable**: Feature importance tells us which features matter most

---

## Part 6: Train / Test Split

### The Golden Rule of Machine Learning

Never evaluate a model on the same data it was trained on.

If you train on 100 samples and test on those SAME 100 samples, the model
gets a perfect score — because it just memorised the answers. This is called
**overfitting**: the model learned the training data but cannot generalise
to new data.

**The solution:** hold out a separate test set the model NEVER sees during training.

```
FULL DATASET (e.g., 27,000 samples)
│
├── TRAINING SET (80%  = 21,600 samples)
│   └── Model sees these. Learns from these. Adjusts its trees to fit these.
│
└── TEST SET (20% = 5,400 samples)
    └── Model NEVER sees these during training.
        We only use these at the end to measure real-world performance.
```

### The 80/20 Split

We use 80% for training and 20% for testing. This is the most common split in
ML research. The split is done by `train_test_split()` in scikit-learn.

### Stratified Splitting — Why It Matters

Without stratification, a random split might accidentally put all vulnerable
samples in the training set and none in the test set:

```
Without stratify:           With stratify=y:
Test set may have:          Test set guaranteed to have:
  - 40 safe samples           - 32 safe samples
  - 0 vulnerable samples      - 8 vulnerable samples
  → Cannot measure recall!    → Can measure all metrics
```

`stratify=y` ensures BOTH the training and test sets have the SAME class ratio
as the full dataset.

### Reproducibility — random_state=42

`random_state=42` is a seed for the random number generator. Using the same
seed guarantees that every time you run the script, you get the **exact same**
train/test split. Without this, each run would produce slightly different splits
and therefore different metric values — making it hard to compare experiments.

The number 42 is conventional (from "The Hitchhiker's Guide to the Galaxy")
but any integer works.

---

## Part 7: Evaluation Metrics

### The Confusion Matrix — The Foundation

Before explaining each metric, understand the **Confusion Matrix**: a 2×2
table counting the four possible outcomes of a binary classifier.

```
                           PREDICTED
                      Safe (0)  Vulnerable (1)
ACTUAL  Safe (0)  |    TN    |      FP      |
        Vuln (1)  |    FN    |      TP      |
```

| Symbol | Full Name | Meaning |
|---|---|---|
| **TP** | True Positive | Vulnerable code correctly flagged as vulnerable |
| **TN** | True Negative | Safe code correctly cleared as safe |
| **FP** | False Positive | Safe code WRONGLY flagged as vulnerable (false alarm) |
| **FN** | False Negative | Vulnerable code WRONGLY cleared as safe (MISSED BUG) |

In security contexts:
- **FN is dangerous**: a real vulnerability slips into production
- **FP is costly**: developer wastes time reviewing safe code

---

### Metric 1: Accuracy

```
Accuracy = (TP + TN) / (TP + TN + FP + FN)
         = Correct predictions / Total predictions
```

**Example:** 90 correct out of 100 → Accuracy = 90%

**Why accuracy can mislead:**
If 90% of the dataset is safe and 10% is vulnerable, a model that ALWAYS
predicts "safe" achieves 90% accuracy — but catches ZERO vulnerabilities.
For security work, always report Precision, Recall, and F1 alongside accuracy.

---

### Metric 2: Precision

```
Precision = TP / (TP + FP)
          = "Of all the code I FLAGGED as vulnerable, how many actually were?"
```

**Example:** Model flagged 50 samples as vulnerable. 45 actually were. Precision = 45/50 = 90%.

**High precision = few false alarms.**
Important when false alarms are costly (developer time is expensive).

---

### Metric 3: Recall (Sensitivity)

```
Recall = TP / (TP + FN)
       = "Of all the REAL vulnerabilities, how many did I catch?"
```

**Example:** 100 real vulnerabilities exist. Model caught 75. Recall = 75/100 = 75%.

**High recall = fewer vulnerabilities missed.**
In security, recall is CRITICALLY important. A missed vulnerability
(FN) is a potential breach in production.

---

### Metric 4: F1 Score

```
F1 = 2 × (Precision × Recall) / (Precision + Recall)
   = The harmonic mean of Precision and Recall
```

**Why harmonic mean instead of average?**
If Precision = 1.0 and Recall = 0.0:
- Arithmetic mean: (1.0 + 0.0) / 2 = 0.5 (looks okay)
- Harmonic mean: 2 × (1.0 × 0.0) / (1.0 + 0.0) = 0.0 (correctly shows failure)

The harmonic mean PUNISHES extreme imbalances between precision and recall.
A high F1 score requires BOTH precision AND recall to be high.

**F1 Score is the primary metric for vulnerability detection research.**

---

### Metric Summary Table

| Metric | Formula | Best value | Worst value | What suffers when it is low |
|---|---|---|---|---|
| Accuracy | (TP+TN)/Total | 1.0 | 0.0 | Overall correctness |
| Precision | TP/(TP+FP) | 1.0 | 0.0 | False alarms (wasted reviews) |
| Recall | TP/(TP+FN) | 1.0 | 0.0 | Missed vulnerabilities |
| F1 Score | harmonic mean | 1.0 | 0.0 | Both false alarms AND missed bugs |

---

## Part 8: Feature Importance

Random Forest provides a **feature importance score** for every feature.
The importance of a feature is the total reduction in node impurity it
contributes, averaged over all 100 trees and weighted by the number of
samples each split affects.

In simple terms: a high-importance feature is one that the model uses
FREQUENTLY and HIGH UP in the trees (early splits are more powerful
because they affect more samples).

### What Feature Importance Reveals

Feature importance answers the question: **"Which of the 792 features does
the model actually care about?"**

**Expected findings in vulnerability detection:**

| Feature type | Expected importance | Reason |
|---|---|---|
| `n_pointer_ops` (AST) | High | Pointer operations are the #1 source of memory bugs |
| `pointer_count` (metric) | High | Direct count of `->` and `*identifier` |
| `n_loops` (AST) | High | Loops without bounds checks → buffer overflow |
| `nesting_depth` (metric) | Medium | Deep nesting hides complex, error-prone logic |
| Individual `embed_XXX` | Low individually | 768 embed features share the signal |
| `embed_XXX` total | High collectively | Together they carry CodeBERT's semantic knowledge |

The fact that individual embed dimensions rank lower than AST/metric features
does not mean CodeBERT is less useful — its 768 dimensions collectively encode
rich semantic signal, but each single dimension carries only 1/768th of that signal.

---

## Part 9: Class Imbalance

### The Devign Dataset Distribution

The Devign dataset is approximately:
- 45% vulnerable (label=1): ~12,292 functions
- 55% safe (label=0): ~15,026 functions

This is relatively balanced. However, many real-world security datasets
have severe imbalance (95% safe, 5% vulnerable).

### How We Handle Imbalance

**Random Forest:** `class_weight="balanced"`
Sets the weight of each class proportional to its inverse frequency:
```
weight_class_i = n_samples / (n_classes × count_class_i)
```
Vulnerable samples get higher weight, so the model pays more attention to them.

**XGBoost:** `scale_pos_weight = n_safe / n_vulnerable`
If there are 3 safe samples for every 1 vulnerable, `scale_pos_weight=3`
tells XGBoost to treat each vulnerable sample as if it appeared 3 times.

**Why this matters:**
Without class balancing, a model might learn to always predict "safe"
because that gives 55% accuracy — but it catches zero vulnerabilities.
Class balancing forces the model to take vulnerable samples seriously.

---

## Part 10: Advantages of These Models

### Random Forest Advantages

| Advantage | Explanation |
|---|---|
| Easy to use | Few hyperparameters; works well with defaults |
| Robust to outliers | Threshold-based splits are not affected by extreme values |
| No feature scaling | Works with raw values; no normalisation needed |
| Feature importance | Built-in measurement of which features matter |
| Low overfitting risk | Bootstrap sampling and random features prevent memorisation |
| Parallelisable | All 100 trees can be trained simultaneously |
| Handles mixed types | Integer and float features treated identically |

### XGBoost Advantages

| Advantage | Explanation |
|---|---|
| Usually higher accuracy | Sequential error correction improves precision |
| Fast training | Highly optimised C++ implementation under the hood |
| Handles missing values | Built-in support for NaN features |
| Regularisation | L1 and L2 regularisation prevent overfitting |
| Wide adoption | Used in most top-performing Kaggle solutions |
| Small model file | JSON format is compact and portable |

---

## Part 11: Limitations

### Random Forest Limitations

| Limitation | Explanation |
|---|---|
| Large model size | 100 trees with 792 features = potentially large .joblib file |
| Slow prediction | Must query all 100 trees for each prediction |
| Poor with high dimensionality | 792 features with few samples risks overfitting |
| Not sequential | Cannot capture temporal patterns in code evolution |
| Black box | Cannot explain a specific prediction in plain language |

### XGBoost Limitations

| Limitation | Explanation |
|---|---|
| More tuning required | learning_rate, max_depth, n_estimators interact |
| Overfitting with small data | Sequential training can memorise training set |
| Sensitive to outliers | Less robust than Random Forest to extreme feature values |
| Black box | Cannot explain why a specific function is flagged |

### Shared Limitations for Vulnerability Detection

| Limitation | Explanation |
|---|---|
| No inter-procedural analysis | Sees one function at a time; misses bugs spanning multiple functions |
| No runtime awareness | Cannot detect race conditions or input-dependent bugs |
| Dataset bias | Learned from FFmpeg/QEMU; may not generalise to other codebases |
| Static analysis only | Cannot detect vulnerabilities triggered by specific inputs |

---

## Part 12: Viva Questions and Answers

---

**Q1. What is Random Forest and how does it make a prediction?**

> Random Forest is an ensemble learning algorithm that trains a large
> number of decision trees (100 in our project) and combines their
> predictions by majority vote. Each tree is trained on a random
> subset of the training samples (bootstrap sampling) and uses a
> random subset of features at each decision node. Because each tree
> sees different data and different features, they make different
> mistakes. When you take the majority vote across all 100 trees,
> the individual mistakes cancel out and the correct signal
> accumulates. For our project, a new C function is represented as
> 792 numbers. All 100 trees independently classify it as vulnerable
> (1) or safe (0). If 73 trees say vulnerable and 27 say safe, the
> final prediction is vulnerable.

---

**Q2. What is XGBoost and how does it differ from Random Forest?**

> XGBoost stands for eXtreme Gradient BOOSTing. Like Random Forest,
> it builds an ensemble of decision trees. The key difference is that
> XGBoost trains trees SEQUENTIALLY rather than independently. The
> first tree makes initial predictions. The second tree specifically
> targets the errors made by the first tree. The third tree corrects
> the remaining errors, and so on. Each new tree reduces the
> residual error of all previous trees combined. The final prediction
> is a weighted sum of all trees' predictions. This sequential error
> correction mechanism is called gradient boosting and tends to
> produce higher accuracy than Random Forest, at the cost of more
> tuning parameters and slightly higher overfitting risk.

---

**Q3. What is the train/test split and why is it necessary?**

> The train/test split divides the dataset into two non-overlapping
> groups. The training set (80% of data) is shown to the model during
> learning. The test set (20% of data) is held completely separate
> and the model never sees it during training. After training, we
> evaluate the model on the test set to get an honest estimate of
> how well it would perform on real-world, unseen code. If we
> evaluated on the training data instead, the model would score
> perfectly by memorising all the examples — a phenomenon called
> overfitting. The test set ensures we are measuring generalisation,
> not memorisation. We also use stratified splitting, which preserves
> the same ratio of vulnerable to safe samples in both the training
> and test sets.

---

**Q4. Explain Precision and Recall. Which is more important for vulnerability detection and why?**

> Precision measures the reliability of the model's positive
> predictions: of all the functions the model flagged as vulnerable,
> what percentage actually were vulnerable? A precision of 0.90 means
> 90% of the flags were genuine vulnerabilities and 10% were false
> alarms.
>
> Recall measures how complete the model's detection is: of all the
> functions that are truly vulnerable, what percentage did the model
> catch? A recall of 0.80 means 80% of real vulnerabilities were
> found and 20% were missed.
>
> For vulnerability detection, Recall is more critical than Precision.
> A missed vulnerability (low recall) means a security flaw enters
> production and could be exploited. A false alarm (low precision)
> means a developer wastes time reviewing safe code — this is
> inconvenient but not dangerous. However, we cannot completely
> sacrifice precision either — if every line of code is flagged,
> developers will ignore the tool entirely. The F1 score, which is
> the harmonic mean of precision and recall, balances both concerns
> and is our primary metric.

---

**Q5. What is F1 Score and why do we use the harmonic mean instead of the arithmetic mean?**

> The F1 Score is defined as 2 times the product of Precision and
> Recall divided by their sum. This formula is called the harmonic
> mean. We prefer the harmonic mean over the arithmetic mean because
> it severely penalises extreme imbalances between precision and
> recall. Consider a model with Precision equal to 1.0 and Recall
> equal to 0.0 — it never predicts vulnerable, so it has no false
> alarms but catches nothing. The arithmetic mean would give 0.5
> (seemingly reasonable), but the harmonic mean gives 0.0
> (correctly indicating the model is useless). The harmonic mean
> forces both precision and recall to be genuinely high before the
> F1 score can be high.

---

**Q6. What is feature importance in Random Forest and what can it tell us about vulnerability detection?**

> Random Forest computes a feature importance score for every one
> of the 792 input features. The score reflects how much each feature
> contributed to reducing impurity in the decision trees, averaged
> across all 100 trees. A feature that appears near the top of many
> trees, and creates clean splits between vulnerable and safe code,
> gets a high importance score.
>
> In our project, we expect pointer-related features like
> `n_pointer_ops` and `pointer_count` to rank highly because pointer
> operations are the primary source of memory-safety vulnerabilities
> in C. Features like `n_loops` and `nesting_depth` should also rank
> high because buffer overflows typically involve loops without bounds
> checks. Individual CodeBERT embedding dimensions tend to rank lower
> individually, but collectively the 768 dimensions represent the
> largest total contribution from any single branch. Feature
> importance serves two purposes: it helps interpret the model's
> decisions, and it can guide future work by identifying which branch
> (AST, metrics, CodeBERT) contributes most to vulnerability detection.

---

**Q7. What is class imbalance and how do you handle it?**

> Class imbalance occurs when one class has significantly more
> samples than the other. In vulnerability detection datasets,
> safe code typically outnumbers vulnerable code. If a dataset has
> 90% safe and 10% vulnerable samples, a model that always predicts
> safe achieves 90% accuracy but catches zero vulnerabilities.
>
> We handle class imbalance in two ways. For Random Forest, we set
> `class_weight="balanced"`, which causes scikit-learn to assign
> higher importance weights to vulnerable samples proportional to
> their underrepresentation. The loss function sees each vulnerable
> sample as more important than each safe sample. For XGBoost, we
> compute `scale_pos_weight` as the ratio of safe to vulnerable
> samples in the training set. If there are three safe samples for
> every vulnerable one, we set `scale_pos_weight=3`, which gives
> each vulnerable sample three times the influence in the gradient
> computation. Additionally, we use stratified splitting to ensure
> the test set has the same class ratio as the full dataset.

---

## Part 13: Expected Output with Real Dataset

When `final_features.csv` is available (after downloading Devign and
running all pipeline scripts), the script produces output similar to:

```
STEP 7: MODEL COMPARISON

  Model              Accuracy  Precision   Recall       F1  Time(s)
  ---------------------------------------------------------------
  Random Forest        0.8234     0.7891   0.8156   0.8022     4.21
  XGBoost              0.8456     0.8102   0.8321   0.8210     2.83

  Best model by F1 Score: XGBoost  (F1 = 0.8210)
```

Note: Actual values depend on dataset size and preprocessing choices.
Research papers on Devign typically report F1 in the range 0.58 to 0.68
for single-modal approaches and 0.70 to 0.78 for multi-modal approaches.
Results above 0.80 may indicate the model has access to a clean dataset
and good feature extraction.

---

## Part 14: How to Run

```powershell
# Step 1: Activate venv
.\venv\Scripts\activate

# Step 2: Navigate to model folder
cd src\model

# Step 3: Run (demo works without dataset)
python train_classifier.py
```

**To run with real data:**
1. Download the Devign dataset (function.json from Microsoft CodeXGLUE)
2. Place it in `dataset/raw/function.json`
3. Run each script in order:
   ```
   Day 4: cd src\preprocessing && python preprocess_dataset.py
   Day 5: cd src\ast           && python extract_ast_features.py
   Day 6: cd src\metrics       && python extract_metrics.py
   Day 7: cd src\codebert      && python extract_embeddings.py
   Day 8: cd src\fusion        && python fuse_features.py
   Day 9: cd src\model         && python train_classifier.py
   ```

---

## Part 15: Saved Files

| File | Location | Description |
|---|---|---|
| `random_forest.joblib` | `models/` | Trained RF model (load with joblib) |
| `xgboost.json` | `models/` | Trained XGBoost model (portable JSON) |
| `training_metadata.json` | `models/` | Config, metrics, feature counts |
| `model_comparison.png` | `results/` | Bar chart: Accuracy/Precision/Recall/F1 |
| `feature_importance.png` | `results/` | Top 20 features by RF importance |

### Loading a Saved Model

```python
import joblib
import numpy as np

# Load the trained Random Forest
model = joblib.load("models/random_forest.joblib")

# features = a 792-number array for one C function
# (produced by the three feature extraction scripts)
features = np.array([...])   # shape (792,)

# Predict class
prediction = model.predict([features])[0]
print("VULNERABLE" if prediction == 1 else "SAFE")

# Predict probability of being vulnerable
probability = model.predict_proba([features])[0][1]
print(f"Confidence: {probability:.1%}")
```

---
*Document prepared on Day 9 — Classifier Training and Evaluation*
