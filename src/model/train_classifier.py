# =============================================================================
# train_classifier.py
# Day 9: Multi-Modal Vulnerability Classifier Training
# Project: Multi-Modal Code Vulnerability Detection Using CodeBERT
# =============================================================================
#
# WHAT DOES THIS SCRIPT DO?
#
#   This is the FINAL modelling step. We take the 792-feature table
#   (final_features.csv, produced by Day 8 fusion) and train two
#   machine learning classifiers that predict:
#
#     Input  : 792 numbers for one C function
#     Output : 0 (non-vulnerable / safe)  OR  1 (vulnerable)
#
#   We train TWO classifiers and compare their performance:
#     1. Random Forest    -- simple, robust, interpretable
#     2. XGBoost          -- more powerful, often more accurate
#
#
# WHAT IS A DECISION TREE? (the building block of both models)
#
#   A decision tree asks a series of YES/NO questions about the features:
#
#     "Is n_loops > 3?"
#         YES --> "Is pointer_count > 5?"
#                     YES --> "Likely VULNERABLE"
#                     NO  --> "Maybe safe, check more..."
#         NO  --> "Is loc > 50?"
#                     YES --> "Could be either..."
#                     NO  --> "Likely SAFE"
#
#   Each question splits the data into two groups.
#   The tree keeps asking questions until it reaches a leaf node
#   (a final answer: vulnerable or safe).
#
#   The tree LEARNS which questions to ask by examining the training data.
#   It searches for the question that best separates vulnerable from safe.
#
#
# WHAT IS RANDOM FOREST?
#
#   A Random Forest trains N_ESTIMATORS (100 by default) decision trees.
#   Each tree is trained on a RANDOM SUBSET of:
#     - The training samples (bootstrap sampling)
#     - The feature columns (random feature selection at each split)
#
#   To classify a new function:
#     - ALL 100 trees make their own prediction (0 or 1)
#     - The MAJORITY VOTE wins (if 67 trees say 1 and 33 say 0 --> output 1)
#
#   Why is this better than one tree?
#     - Each tree makes different mistakes (because it saw different data)
#     - The mistakes CANCEL OUT when you take the majority vote
#     - The correct signal REINFORCES across all trees
#   This is called ENSEMBLE LEARNING.
#
#
# WHAT IS XGBOOST?
#
#   XGBoost (eXtreme Gradient BOOSTing) also uses many decision trees,
#   but trains them SEQUENTIALLY rather than independently:
#
#     Tree 1 : Makes predictions, calculates errors (residuals)
#     Tree 2 : Specifically trained to FIX the errors of Tree 1
#     Tree 3 : Specifically trained to fix the remaining errors
#     ...
#     Tree 100: Each tree is a small correction to the combined model so far
#
#   Final prediction = weighted sum of all 100 trees' predictions.
#
#   XGBoost is usually MORE ACCURATE than Random Forest because each
#   new tree actively learns from the previous trees' mistakes.
#   However, it needs more careful tuning of parameters like
#   learning_rate, max_depth, etc.
#
#
# EVALUATION METRICS:
#
#   After training, we test the model on the HELD-OUT test set
#   (20% of data the model has NEVER seen before).
#
#   We report 4 metrics:
#
#   ACCURACY  = (correctly classified samples) / (total samples)
#               Easy to understand, but can be misleading if data is imbalanced.
#               Example: If 90% of samples are safe, always predicting "safe"
#                        gives 90% accuracy but catches 0% of vulnerabilities.
#
#   PRECISION = (correctly flagged vulnerable) / (all flagged as vulnerable)
#               "Of the functions I SAID were vulnerable, how many actually were?"
#               Low precision = many false alarms (safe code wrongly flagged).
#
#   RECALL    = (correctly flagged vulnerable) / (all truly vulnerable)
#               "Of all the REAL vulnerabilities, how many did I catch?"
#               Low recall = vulnerabilities missed (dangerous!).
#
#   F1 SCORE  = 2 * (Precision * Recall) / (Precision + Recall)
#               The harmonic mean of precision and recall.
#               Balances both metrics into one number.
#               This is the PRIMARY metric for vulnerability detection.
#               A high F1 means BOTH precision and recall are good.
#
#
# HOW TO RUN:
#   1. Activate venv:  .\venv\Scripts\activate
#   2. Navigate:       cd src\model
#   3. Run:            python train_classifier.py
#
# PREREQUISITE:
#   dataset/processed/final_features.csv   (produced by Day 8)
#
# PACKAGES (all installed):
#   scikit-learn : Random Forest, metrics, train_test_split
#   xgboost      : XGBoost classifier
#   joblib       : save/load sklearn models
#   matplotlib   : save comparison chart
# =============================================================================


# ── SECTION 0: IMPORTS ────────────────────────────────────────────────────────

import os           # file paths and folder creation
import sys          # sys.exit() to stop cleanly
import json         # save training metadata as JSON
import time         # measure training time

import numpy  as np
import pandas as pd

# -- scikit-learn: the core ML library ----------------------------------------
# train_test_split : divides dataset into training and testing portions
# RandomForestClassifier : the Random Forest model
# accuracy_score etc.    : functions to compute evaluation metrics

from sklearn.model_selection import train_test_split
from sklearn.ensemble        import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)
import joblib   # saves and loads scikit-learn model objects to disk

# -- matplotlib (for saving comparison chart) ---------------------------------
# "Agg" backend means "write to file" (no interactive window needed)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

# -- XGBoost ------------------------------------------------------------------
# We try to import XGBoost. If the import fails, we train Random Forest only.
try:
    from xgboost import XGBClassifier
    XGBOOST_OK = True
except ImportError:
    XGBOOST_OK = False


# ── SECTION 1: CONSTANTS ─────────────────────────────────────────────────────
#
# All tunable values are defined here so you only need to change ONE place.

TEST_SIZE    = 0.20  # 20% of data used for testing, 80% for training
RANDOM_STATE = 42    # random seed -- ensures the SAME split every run
                     # (random_state=42 is used by convention in ML research)
N_ESTIMATORS = 100   # number of decision trees in the ensemble

# Metadata columns from final_features.csv that are NOT features
METADATA_COLS = ["sample_id", "target", "project", "commit_id"]


# ── SECTION 2: PATH SETUP ────────────────────────────────────────────────────

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT  = os.path.dirname(os.path.dirname(SCRIPT_DIR))

PROCESSED_DIR = os.path.join(PROJECT_ROOT, "dataset", "processed")
MODELS_DIR    = os.path.join(PROJECT_ROOT, "models")
RESULTS_DIR   = os.path.join(PROJECT_ROOT, "results")

FINAL_CSV     = os.path.join(PROCESSED_DIR, "final_features.csv")
RF_MODEL_PATH = os.path.join(MODELS_DIR, "random_forest.joblib")
XGB_MODEL_PATH= os.path.join(MODELS_DIR, "xgboost.json")
META_JSON     = os.path.join(MODELS_DIR, "training_metadata.json")
CHART_PATH    = os.path.join(RESULTS_DIR, "model_comparison.png")
FIMP_PATH     = os.path.join(RESULTS_DIR, "feature_importance.png")


# ── SECTION 3: UTILITY FUNCTIONS ─────────────────────────────────────────────

def section(title):
    """Prints a visible divider for each major output section."""
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


def print_metrics_table(metrics_dict):
    """
    Print accuracy, precision, recall, F1 in a tidy table.
    Also prints a text-based confusion matrix.

    Parameters:
        metrics_dict : dict returned by evaluate_model()
    """
    name = metrics_dict["name"]
    print(f"\n  Model         : {name}")
    print(f"  Training time : {metrics_dict['train_time']:.2f} seconds")
    print()
    print(f"  {'Metric':<12} {'Value':>8}   Meaning")
    print(f"  {'-'*55}")
    print(f"  {'Accuracy':<12} {metrics_dict['accuracy']:>8.4f}   "
          f"({metrics_dict['accuracy']*100:.1f}% of all samples correct)")
    print(f"  {'Precision':<12} {metrics_dict['precision']:>8.4f}   "
          f"Of all I flagged as vuln, {metrics_dict['precision']*100:.1f}% were truly vuln")
    print(f"  {'Recall':<12} {metrics_dict['recall']:>8.4f}   "
          f"Of all real vulns, I caught {metrics_dict['recall']*100:.1f}%")
    print(f"  {'F1 Score':<12} {metrics_dict['f1']:>8.4f}   "
          f"Harmonic mean of precision and recall")

    # Confusion matrix
    cm  = metrics_dict["cm"]
    tn  = cm[0][0]   # True Negative  : safe, correctly predicted safe
    fp  = cm[0][1]   # False Positive : safe, wrongly predicted vulnerable
    fn  = cm[1][0]   # False Negative : vulnerable, wrongly predicted safe
    tp  = cm[1][1]   # True Positive  : vulnerable, correctly predicted vulnerable

    print()
    print("  CONFUSION MATRIX:")
    print("                        Predicted")
    print("                    Safe    Vuln")
    print(f"  Actual Safe  |  {tn:5d}   {fp:5d}  |")
    print(f"  Actual Vuln  |  {fn:5d}   {tp:5d}  |")
    print()
    print(f"  TP = {tp:4d}  (vulnerable CAUGHT   -- good)")
    print(f"  TN = {tn:4d}  (safe      CLEARED   -- good)")
    print(f"  FP = {fp:4d}  (safe wrongly FLAGGED -- false alarm)")
    print(f"  FN = {fn:4d}  (vulnerable MISSED   -- DANGEROUS)")


def evaluate_model(model, X_train, X_test, y_train, y_test, name):
    """
    Train a model and return a dict of evaluation metrics.

    Parameters:
        model    : an UNFITTED sklearn/xgboost classifier
        X_train  : training feature matrix  (numpy array)
        X_test   : test feature matrix      (numpy array)
        y_train  : training labels (0/1)    (numpy array)
        y_test   : test labels (0/1)        (numpy array)
        name     : string label for printing

    Returns:
        dict with keys: name, accuracy, precision, recall, f1,
                        train_time, cm (confusion matrix as list)
    """
    # -- Train ----------------------------------------------------------------
    # model.fit(X, y) is the CORE training call.
    # It examines X_train and y_train together and adjusts the model's
    # internal parameters (the tree structures, thresholds) to make
    # good predictions.
    t0 = time.time()
    model.fit(X_train, y_train)
    elapsed = time.time() - t0

    # -- Predict on the TEST set (data the model has NEVER seen) --------------
    # model.predict(X_test) returns a 1-D array of predictions [0, 1, 0, ...]
    # one value per sample in X_test.
    y_pred = model.predict(X_test)

    # -- Compute metrics ------------------------------------------------------
    acc  = accuracy_score(y_test, y_pred)
    # accuracy_score: (number of correct predictions) / (total predictions)

    prec = precision_score(y_test, y_pred, zero_division=0)
    # precision_score: TP / (TP + FP)
    # zero_division=0 prevents a warning if the model never predicts class 1

    rec  = recall_score(y_test, y_pred, zero_division=0)
    # recall_score: TP / (TP + FN)

    f1   = f1_score(y_test, y_pred, zero_division=0)
    # f1_score: 2 * (precision * recall) / (precision + recall)

    cm   = confusion_matrix(y_test, y_pred, labels=[0, 1])
    # confusion_matrix produces a 2x2 table:
    # [[TN, FP],
    #  [FN, TP]]
    # labels=[0,1] ensures the matrix is always 2x2 even if a class is absent

    return {
        "name"      : name,
        "model"     : model,
        "accuracy"  : round(float(acc),  4),
        "precision" : round(float(prec), 4),
        "recall"    : round(float(rec),  4),
        "f1"        : round(float(f1),   4),
        "train_time": round(elapsed, 2),
        "cm"        : cm.tolist(),
    }


# =============================================================================
# STEP 1: DEMO -- FULL PIPELINE ON SYNTHETIC DATA
# =============================================================================
#
# This section ALWAYS runs, even without the real dataset.
# It creates 400 synthetic C-function representations and shows the
# complete training pipeline: load -> split -> train -> evaluate -> compare.
#
# The synthetic data is designed to HAVE a clear signal so that the
# models achieve good metrics, demonstrating what you will see with real data.
#
# Feature layout in the demo (30 features, named to match real features):
#   Features  0-9  : AST-like (integers 0-10)
#   Features 10-19 : Metric-like (integers 0-50)
#   Features 20-29 : Embed-like (floats ~ -2 to +2)
# =============================================================================

section("STEP 1: DEMO -- SYNTHETIC DATA PIPELINE")

print()
print("  This demo creates 400 synthetic C-function samples and trains")
print("  both classifiers. It shows the COMPLETE pipeline before we")
print("  run on the real Devign dataset.")
print()
print("  Synthetic feature layout: 30 features")
print("    Features  0- 9 : AST-like  (e.g., n_loops, n_pointer_ops)")
print("    Features 10-19 : Metric-like (e.g., loc, pointer_count)")
print("    Features 20-29 : Embed-like  (e.g., embed_000 ... embed_009)")
print()

# ── Create synthetic dataset ──────────────────────────────────────────────────
#
# We build TWO groups of samples:
#   GROUP 0 (safe, label=0):       240 samples
#   GROUP 1 (vulnerable, label=1): 160 samples
# Total: 400 samples.   Class split: 60% safe / 40% vulnerable.
#
# Vulnerable samples have:
#   - Higher AST counts (more loops, more pointer ops)
#   - Higher metric values (larger functions, more operators)
#   - A DIFFERENT cluster in embedding space

np.random.seed(RANDOM_STATE)

N_SAFE  = 240
N_VULN  = 160
N_DEMO_FEAT = 30   # 10 AST + 10 metric + 10 embed

# Safe samples: low loop counts, moderate metrics, embedding near -0.2
safe_ast   = np.random.randint(0,  4, (N_SAFE, 10)).astype(float)
safe_met   = np.random.randint(5, 20, (N_SAFE, 10)).astype(float)
safe_emb   = np.random.randn(N_SAFE, 10) * 0.4 - 0.2

# Vulnerable samples: higher loop counts, larger functions, diff embedding
vuln_ast   = np.random.randint(3, 10, (N_VULN, 10)).astype(float)
vuln_met   = np.random.randint(15,45, (N_VULN, 10)).astype(float)
vuln_emb   = np.random.randn(N_VULN, 10) * 0.4 + 0.4

X_safe = np.hstack([safe_ast, safe_met, safe_emb])
X_vuln = np.hstack([vuln_ast, vuln_met, vuln_emb])

X_demo = np.vstack([X_safe, X_vuln])
y_demo = np.array([0] * N_SAFE + [1] * N_VULN)

# Shuffle so safe/vulnerable are not all in a row
perm   = np.random.permutation(len(y_demo))
X_demo = X_demo[perm]
y_demo = y_demo[perm]

print(f"  Demo dataset shape    : {X_demo.shape}  ({len(X_demo)} samples x {N_DEMO_FEAT} features)")
print(f"  Non-Vulnerable (0)    : {N_SAFE}  samples")
print(f"  Vulnerable     (1)    : {N_VULN}  samples")

# ── Demo train/test split ─────────────────────────────────────────────────────
#
# train_test_split() randomly divides the data into two groups:
#   Training set : the model sees this data during training
#   Test set     : held back, used ONLY to evaluate the trained model
#
# Parameters:
#   test_size=0.20  : 20% of data goes to the test set (80 samples here)
#   random_state=42 : random seed -- same split every run for reproducibility
#   stratify=y_demo : ensures BOTH splits have the same class ratio
#                     (without stratify, the test set might be all-safe or all-vuln)

Xd_tr, Xd_te, yd_tr, yd_te = train_test_split(
    X_demo, y_demo,
    test_size=TEST_SIZE,
    random_state=RANDOM_STATE,
    stratify=y_demo,   # preserve 60/40 ratio in both train and test
)

print()
print(f"  Train/Test split (80/20 stratified):")
print(f"    Training samples : {len(Xd_tr)}  "
      f"(non-vuln={sum(yd_tr==0)}, vuln={sum(yd_tr==1)})")
print(f"    Test samples     : {len(Xd_te)}  "
      f"(non-vuln={sum(yd_te==0)}, vuln={sum(yd_te==1)})")

# ── Demo: Train Random Forest ─────────────────────────────────────────────────
print()
print("  Training Random Forest on synthetic data...")

rf_demo = RandomForestClassifier(
    n_estimators=50,          # 50 trees is enough for the demo
    max_features="sqrt",      # at each split, try sqrt(30) ~ 5 features
    class_weight="balanced",  # gives more weight to the minority class
    random_state=RANDOM_STATE,
    n_jobs=-1,                # use all CPU cores for parallel tree building
)
demo_rf_metrics = evaluate_model(rf_demo, Xd_tr, Xd_te, yd_tr, yd_te, "Random Forest (DEMO)")
print_metrics_table(demo_rf_metrics)

# ── Demo: Train XGBoost ───────────────────────────────────────────────────────
if XGBOOST_OK:
    n_neg = int((y_demo == 0).sum())
    n_pos = int((y_demo == 1).sum())
    spw   = round(n_neg / n_pos, 2)   # scale_pos_weight for class balance

    print()
    print("  Training XGBoost on synthetic data...")

    xgb_demo = XGBClassifier(
        n_estimators=50,
        max_depth=4,
        learning_rate=0.1,
        scale_pos_weight=spw,  # compensates for class imbalance
        random_state=RANDOM_STATE,
        verbosity=0,           # suppress XGBoost's own output
    )
    demo_xgb_metrics = evaluate_model(
        xgb_demo, Xd_tr, Xd_te, yd_tr, yd_te, "XGBoost (DEMO)"
    )
    print_metrics_table(demo_xgb_metrics)

    print()
    print("  DEMO COMPARISON:")
    print(f"  {'Model':<20} {'Accuracy':>9} {'Precision':>10} {'Recall':>8} {'F1':>8}")
    print(f"  {'-'*58}")
    for m in [demo_rf_metrics, demo_xgb_metrics]:
        print(f"  {m['name']:<20} {m['accuracy']:>9.4f} {m['precision']:>10.4f}"
              f" {m['recall']:>8.4f} {m['f1']:>8.4f}")

print()
print("  DEMO COMPLETE.")
print("  The demo above shows the pipeline working on synthetic data.")
print("  Loading real Devign data next...")


# =============================================================================
# STEP 2: LOAD THE REAL DATASET (final_features.csv)
# =============================================================================

section("STEP 2: LOADING final_features.csv")

if not os.path.exists(FINAL_CSV):
    print(f"  WARNING: final_features.csv not found at:")
    print(f"    {FINAL_CSV}")
    print()
    print("  To generate it, run these scripts in order:")
    print("    Day 4: cd src\\preprocessing && python preprocess_dataset.py")
    print("    Day 5: cd src\\ast           && python extract_ast_features.py")
    print("    Day 6: cd src\\metrics       && python extract_metrics.py")
    print("    Day 7: cd src\\codebert      && python extract_embeddings.py")
    print("    Day 8: cd src\\fusion        && python fuse_features.py")
    print()
    print("  The DEMO above completed successfully.")
    print("  Exiting. Re-run after generating the feature file.")
    sys.exit(0)

# pd.read_csv() loads the CSV into a DataFrame (table in memory).
df = pd.read_csv(FINAL_CSV, encoding="utf-8")

print(f"  Loaded : {FINAL_CSV}")
print(f"  Rows   : {len(df)}")
print(f"  Columns: {len(df.columns)}")
print()

# Show label distribution
label_counts = df["target"].value_counts().sort_index()
print("  Label distribution:")
for lbl, cnt in label_counts.items():
    pct  = cnt / len(df) * 100
    name = "Vulnerable (1)" if lbl == 1 else "Safe       (0)"
    bar  = "#" * int(pct / 2)
    print(f"    {name}: {cnt:5d}  ({pct:.1f}%)  {bar}")


# =============================================================================
# STEP 3: PREPARE FEATURE MATRIX (X) AND LABEL VECTOR (y)
# =============================================================================

section("STEP 3: PREPARING FEATURES AND LABELS")

print("  Separating columns into features (X) and labels (y).")
print()
print("  METADATA columns (NOT used as features):")
for col in METADATA_COLS:
    if col in df.columns:
        print(f"    {col}")

# y = the TARGET column (what we are trying to predict)
# .values converts the pandas Series to a numpy array [0, 1, 0, 1, ...]
y = df["target"].values

# X = ALL columns EXCEPT the metadata columns
# We keep only the actual feature columns (11 AST + 13 metrics + 768 embeddings)
feature_cols = [col for col in df.columns if col not in METADATA_COLS]
X = df[feature_cols].values

# X has shape (n_samples, n_features) = (rows, columns)
# y has shape (n_samples,)             = (rows,)
print()
print(f"  Feature matrix X : shape {X.shape}")
print(f"    {X.shape[0]} samples (rows)")
print(f"    {X.shape[1]} features (columns)")
print()
print(f"  Label vector y   : shape {y.shape}")
print(f"    {int((y==0).sum())} safe      (label = 0)")
print(f"    {int((y==1).sum())} vulnerable (label = 1)")

# -- Check for NaN in X -------------------------------------------------------
n_nan = int(np.isnan(X).sum())
if n_nan > 0:
    print(f"\n  WARNING: {n_nan} NaN values in feature matrix. Filling with 0.")
    X = np.nan_to_num(X, nan=0.0)
    # np.nan_to_num replaces NaN with 0, +inf with a large number, -inf with a small one
else:
    print(f"  No NaN values in feature matrix.")

# -- Feature column breakdown -------------------------------------------------
ast_cols   = [c for c in feature_cols if c.startswith("n_") or c == "max_depth"]
met_cols   = [c for c in feature_cols if c in [
    "loc","function_count","loop_count","if_count","return_count",
    "avg_line_length","max_line_length","comment_count",
    "total_lines","blank_lines","nesting_depth","operator_count","pointer_count"
]]
emb_cols   = [c for c in feature_cols if c.startswith("embed_")]

print()
print("  Feature column breakdown:")
print(f"    AST features      : {len(ast_cols)}")
print(f"    Metric features   : {len(met_cols)}")
print(f"    CodeBERT embed    : {len(emb_cols)}")
print(f"    TOTAL             : {len(feature_cols)}")


# =============================================================================
# STEP 4: TRAIN / TEST SPLIT
# =============================================================================

section("STEP 4: TRAIN / TEST SPLIT  (80% train, 20% test)")

# train_test_split() randomly divides data into two non-overlapping sets.
#
# WHY SPLIT THE DATA?
#   If we trained and tested on the SAME data, the model would score perfectly
#   (it just memorised the answers). We need to test on data the model has
#   NEVER SEEN to get an honest estimate of real-world performance.
#
# WHAT IS STRATIFIED SPLITTING?
#   Without stratify, a small test set might accidentally have all safe
#   samples and no vulnerable ones. stratify=y ensures BOTH the training
#   and test sets have the SAME proportion of vulnerable and safe samples
#   as the full dataset.
#
# random_state=42:
#   Makes the split REPRODUCIBLE. If you run this script 10 times, you
#   will always get the EXACT same train/test division (because the
#   random number generator starts from the same seed each time).

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=TEST_SIZE,        # 20% of data for testing
    random_state=RANDOM_STATE,  # for reproducibility
    stratify=y,                 # preserve class ratio
)

print(f"  Total samples   : {len(X)}")
print(f"  Training set    : {len(X_train)} samples  ({(1-TEST_SIZE)*100:.0f}%)")
print(f"    Non-vuln (0)  : {int((y_train==0).sum())}")
print(f"    Vulnerable (1): {int((y_train==1).sum())}")
print()
print(f"  Test set        : {len(X_test)} samples  ({TEST_SIZE*100:.0f}%)")
print(f"    Non-vuln (0)  : {int((y_test==0).sum())}")
print(f"    Vulnerable (1): {int((y_test==1).sum())}")

if len(X) < 500:
    print()
    print(f"  NOTE: Only {len(X)} samples available. This usually means")
    print(f"  MAX_SAMPLES was set to a small number in extract_embeddings.py.")
    print(f"  Metrics below are illustrative rather than representative.")
    print(f"  For the full dataset: set MAX_SAMPLES=None in extract_embeddings.py")
    print(f"  and re-run the pipeline (a GPU will finish fastest).")


# =============================================================================
# STEP 5: TRAIN RANDOM FOREST
# =============================================================================

section("STEP 5: TRAINING RANDOM FOREST")

# -- Compute scale_pos_weight for class imbalance ----------------------------
#
# If the dataset has more safe samples than vulnerable ones, the classifier
# will bias towards predicting "safe" because that gets more predictions right.
#
# class_weight="balanced" corrects this: it assigns HIGHER weight (importance)
# to the minority class (vulnerable) so the model takes it seriously.
#
# In scikit-learn, "balanced" sets the weight of class i to:
#   n_samples / (n_classes * count_of_class_i)
# So the minority class (usually vulnerable) gets a higher weight.

print(f"  Random Forest configuration:")
print(f"    n_estimators  : {N_ESTIMATORS}  (number of trees)")
print(f"    max_features  : sqrt  (features tested at each split = sqrt({X.shape[1]}) ~ {int(X.shape[1]**0.5)})")
print(f"    class_weight  : balanced  (corrects for class imbalance)")
print(f"    n_jobs        : -1  (use ALL available CPU cores)")
print(f"    random_state  : {RANDOM_STATE}")
print()
print(f"  Training... (this takes a few seconds on CPU)")

rf_model = RandomForestClassifier(
    n_estimators=N_ESTIMATORS,
    max_features="sqrt",
    # "sqrt" means: at each split, choose the best feature from
    # a RANDOM SUBSET of sqrt(n_features) features.
    # This randomness is what makes the trees DIVERSE (different from each other).

    class_weight="balanced",
    # Gives more importance to the minority class (vulnerable)
    # to prevent the model from ignoring it.

    random_state=RANDOM_STATE,
    # Fixes the random seed so results are reproducible.

    n_jobs=-1,
    # -1 means "use all CPU cores". Each tree can be built independently,
    # so parallel processing speeds up training significantly.
)

rf_metrics = evaluate_model(
    rf_model, X_train, X_test, y_train, y_test,
    name="Random Forest"
)
print_metrics_table(rf_metrics)


# =============================================================================
# STEP 6: TRAIN XGBOOST
# =============================================================================

section("STEP 6: TRAINING XGBOOST")

if not XGBOOST_OK:
    print("  XGBoost is not installed.")
    print("  Install it with:  pip install xgboost")
    print("  Skipping XGBoost training.")
    xgb_metrics = None
else:
    # -- Compute class imbalance ratio ----------------------------------------
    n_safe_train = int((y_train == 0).sum())
    n_vuln_train = int((y_train == 1).sum())
    scale_pos_weight = round(n_safe_train / max(n_vuln_train, 1), 2)
    # scale_pos_weight: how much MORE weight to give the positive (vulnerable) class.
    # If there are 3x as many safe samples as vulnerable, set this to 3.
    # XGBoost equivalent of class_weight="balanced" in scikit-learn.

    print(f"  XGBoost configuration:")
    print(f"    n_estimators    : {N_ESTIMATORS}  (number of sequential trees)")
    print(f"    max_depth       : 6  (max depth of each tree)")
    print(f"    learning_rate   : 0.1  (how much each tree corrects the previous)")
    print(f"                         smaller = more trees needed but safer from overfitting")
    print(f"    scale_pos_weight: {scale_pos_weight}  (safe:vuln ratio for class balance)")
    print(f"    verbosity       : 0  (silent -- suppress XGBoost's own output)")
    print()
    print(f"  Training... (usually faster than Random Forest)")

    xgb_model = XGBClassifier(
        n_estimators=N_ESTIMATORS,
        # Number of boosting rounds (trees). More rounds = better fit
        # but also more risk of overfitting.

        max_depth=6,
        # Maximum depth of each decision tree.
        # Deeper trees learn more specific patterns (can overfit).
        # 6 is a standard default.

        learning_rate=0.1,
        # Also called "eta". Each tree contributes only 10% of its prediction.
        # Lower learning_rate requires more trees but generalises better.

        scale_pos_weight=scale_pos_weight,
        # Increases the weight of positive (vulnerable) samples.
        # Helps when there are more safe samples than vulnerable ones.

        random_state=RANDOM_STATE,
        verbosity=0,
        # 0 = completely silent output from XGBoost itself
    )

    xgb_metrics = evaluate_model(
        xgb_model, X_train, X_test, y_train, y_test,
        name="XGBoost"
    )
    print_metrics_table(xgb_metrics)


# =============================================================================
# STEP 7: COMPARE BOTH MODELS
# =============================================================================

section("STEP 7: MODEL COMPARISON")

results = [rf_metrics]
if xgb_metrics:
    results.append(xgb_metrics)

print()
print(f"  {'Model':<18} {'Accuracy':>9} {'Precision':>10} {'Recall':>8} "
      f"{'F1':>8} {'Time(s)':>8}")
print(f"  {'-'*65}")
for m in results:
    print(f"  {m['name']:<18} {m['accuracy']:>9.4f} {m['precision']:>10.4f} "
          f"{m['recall']:>8.4f} {m['f1']:>8.4f} {m['train_time']:>8.2f}")

# -- Determine best model by F1 -----------------------------------------------
#
# F1 Score is the PRIMARY metric for vulnerability detection because it
# balances precision (avoid false alarms) and recall (avoid missing bugs).
# Accuracy alone can be misleading if the class distribution is skewed.

best = max(results, key=lambda m: m["f1"])
print()
print(f"  Best model by F1 Score: {best['name']}  (F1 = {best['f1']:.4f})")
print()

# -- Interpretation guide -----------------------------------------------------
print("  HOW TO INTERPRET:")
print()
print("  Accuracy:  Overall correctness. A model that always says 'safe'")
print("             gets high accuracy if 90% of samples are safe.")
print("             Do NOT use accuracy alone for security tasks.")
print()
print("  Precision: Reliability of POSITIVE predictions (vulnerable flags).")
print("             Low precision = many false alarms.")
print("             False alarm: developer wastes time reviewing safe code.")
print()
print("  Recall:    Coverage of REAL vulnerabilities.")
print("             Low recall = vulnerabilities MISSED.")
print("             Missed vulnerability = security risk in production.")
print()
print("  F1 Score:  The balance between precision and recall.")
print("             Use F1 as the MAIN metric to choose between models.")

# -- Save comparison chart (bar chart) ----------------------------------------
if MATPLOTLIB_OK:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))

    metric_names  = ["Accuracy", "Precision", "Recall", "F1 Score"]
    metric_keys   = ["accuracy", "precision", "recall", "f1"]
    model_names   = [m["name"] for m in results]
    n_models      = len(results)
    bar_width     = 0.35
    x             = np.arange(len(metric_names))

    colours = ["#2196F3", "#FF5722"]   # blue for RF, orange for XGB
    for i, m in enumerate(results):
        vals = [m[k] for k in metric_keys]
        offset = (i - n_models / 2 + 0.5) * bar_width
        bars = ax.bar(x + offset, vals, bar_width, label=m["name"],
                      color=colours[i % len(colours)], alpha=0.85)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                    f"{val:.3f}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(metric_names)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Score")
    ax.set_title("Model Comparison: Random Forest vs XGBoost\n"
                 "Multi-Modal Code Vulnerability Detection")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=150)
    plt.close()
    print()
    print(f"  Comparison chart saved: {CHART_PATH}")


# =============================================================================
# STEP 8: FEATURE IMPORTANCE (Random Forest)
# =============================================================================

section("STEP 8: FEATURE IMPORTANCE -- TOP 20 FEATURES")

print()
print("  Random Forest computes a 'feature importance' score for every")
print("  feature. A higher score means the feature was used MORE OFTEN")
print("  and at HIGHER POSITIONS in the decision trees, i.e., it split")
print("  the data more cleanly into vulnerable vs safe.")
print()
print("  This tells us: which of the 792 features matter most?")
print()

# rf_model.feature_importances_ is an array of length n_features.
# Each value is between 0 and 1 and they sum to 1.
# A value of 0.05 means this feature was responsible for 5% of the
# information gain across all 100 trees.
importances = rf_model.feature_importances_

# argsort() returns the INDICES that would sort the array.
# [::-1] reverses it (largest first).
# [:20]  keeps only the top 20 indices.
top20_idx   = np.argsort(importances)[::-1][:20]

print(f"  {'Rank':<5} {'Feature':<28} {'Importance':>11}   Feature Type")
print(f"  {'-'*65}")
for rank, idx in enumerate(top20_idx, start=1):
    fname = feature_cols[idx]
    imp   = importances[idx]

    if fname.startswith("embed_"):
        ftype = "CodeBERT embedding"
    elif fname.startswith("n_") or fname in ["max_depth"]:
        ftype = "AST feature"
    else:
        ftype = "Metric feature"

    print(f"  {rank:<5} {fname:<28} {imp:>11.6f}   {ftype}")

print()
print(f"  Total importance of top 20 features: "
      f"{importances[top20_idx].sum()*100:.1f}% of all decisions")

# -- Feature importance bar chart ---------------------------------------------
if MATPLOTLIB_OK:
    fig, ax = plt.subplots(figsize=(10, 6))
    top20_names = [feature_cols[i] for i in top20_idx]
    top20_vals  = importances[top20_idx]

    colours_imp = ["#FF5722" if n.startswith("embed_") else
                   "#2196F3" if n.startswith("n_") or n == "max_depth" else
                   "#4CAF50" for n in top20_names]

    ax.barh(range(20), top20_vals[::-1], color=colours_imp[::-1], alpha=0.85)
    ax.set_yticks(range(20))
    ax.set_yticklabels(top20_names[::-1], fontsize=8)
    ax.set_xlabel("Feature Importance Score")
    ax.set_title("Top 20 Most Important Features (Random Forest)\n"
                 "Blue=AST  Green=Metric  Orange=CodeBERT Embed")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIMP_PATH, dpi=150)
    plt.close()
    print(f"  Feature importance chart saved: {FIMP_PATH}")


# =============================================================================
# STEP 9: SAVE TRAINED MODELS
# =============================================================================

section("STEP 9: SAVING TRAINED MODELS")

os.makedirs(MODELS_DIR, exist_ok=True)

# -- Save Random Forest -------------------------------------------------------
# joblib.dump() serialises the model object to a binary file.
# joblib is part of scikit-learn and is the RECOMMENDED way to save sklearn
# models. It handles numpy arrays inside the model efficiently.
# Loading later: model = joblib.load(RF_MODEL_PATH)

joblib.dump(rf_model, RF_MODEL_PATH)
rf_size_kb = os.path.getsize(RF_MODEL_PATH) / 1024
print(f"  Random Forest saved : {RF_MODEL_PATH}")
print(f"  File size           : {rf_size_kb:.0f} KB")

# -- Save XGBoost -------------------------------------------------------------
if xgb_metrics:
    # XGBoost has its OWN save format (JSON). It is more portable than
    # joblib (can be loaded by XGBoost in Python, R, C++, etc.)
    # Loading later: model = XGBClassifier(); model.load_model(XGB_MODEL_PATH)
    xgb_model.save_model(XGB_MODEL_PATH)
    xgb_size_kb = os.path.getsize(XGB_MODEL_PATH) / 1024
    print()
    print(f"  XGBoost saved       : {XGB_MODEL_PATH}")
    print(f"  File size           : {xgb_size_kb:.0f} KB")

# -- Save training metadata (JSON) --------------------------------------------
#
# We save a JSON file recording what parameters were used and what
# metrics were achieved. This is good practice: you can look at this
# file later and remember exactly how the model was trained.

metadata = {
    "dataset"      : FINAL_CSV,
    "n_samples"    : int(len(X)),
    "n_features"   : int(X.shape[1]),
    "n_train"      : int(len(X_train)),
    "n_test"       : int(len(X_test)),
    "test_size"    : TEST_SIZE,
    "random_state" : RANDOM_STATE,
    "n_estimators" : N_ESTIMATORS,
    "feature_breakdown": {
        "ast"     : len(ast_cols),
        "metrics" : len(met_cols),
        "embeddings": len(emb_cols),
        "total"   : len(feature_cols),
    },
    "random_forest": {k: v for k, v in rf_metrics.items() if k not in ["model","cm"]},
}
if xgb_metrics:
    metadata["xgboost"] = {k: v for k, v in xgb_metrics.items() if k not in ["model","cm"]}

with open(META_JSON, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)

print()
print(f"  Training metadata   : {META_JSON}")


# -- How to load and use a saved model ----------------------------------------
print()
print("  To load and use the Random Forest in a new script:")
print()
print("    import joblib, numpy as np")
print(f"    model = joblib.load(r'{RF_MODEL_PATH}')")
print("    # features = your 792-feature vector (1D numpy array)")
print("    prediction = model.predict([features])")
print("    probability = model.predict_proba([features])[0][1]")
print("    print('Vulnerable' if prediction[0] == 1 else 'Safe')")
print("    print(f'Confidence: {probability:.2%}')")


# =============================================================================
# DONE
# =============================================================================

section("CLASSIFIER TRAINING COMPLETE")

print(f"  Dataset          : {FINAL_CSV}")
print(f"  Samples          : {len(X)}")
print(f"  Features         : {X.shape[1]}  (11 AST + 13 Metrics + 768 CodeBERT)")
print()
print("  Results:")
print(f"  {'Model':<18} {'Accuracy':>9} {'Precision':>10} {'Recall':>8} {'F1':>8}")
print(f"  {'-'*55}")
for m in results:
    print(f"  {m['name']:<18} {m['accuracy']:>9.4f} {m['precision']:>10.4f}"
          f" {m['recall']:>8.4f} {m['f1']:>8.4f}")
print()
print("  Saved files:")
print(f"    {RF_MODEL_PATH}")
if xgb_metrics:
    print(f"    {XGB_MODEL_PATH}")
print(f"    {META_JSON}")
if MATPLOTLIB_OK:
    print(f"    {CHART_PATH}")
    print(f"    {FIMP_PATH}")
print()
print("  Next step:")
print("    Day 10 -- Build the Streamlit web application")
print("              Load saved models and classify new C functions")
print()
