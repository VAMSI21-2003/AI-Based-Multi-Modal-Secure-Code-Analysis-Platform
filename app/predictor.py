# =============================================================================
# predictor.py
# Day 12: Streamlit App -- Prediction Engine
# Project: Multi-Modal Code Vulnerability Detection Using CodeBERT
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   This file handles everything related to loading models and running
#   predictions. It bridges utils.py (feature extraction) and app.py (UI).
#
#   It is "pure Python" -- no Streamlit imports. This keeps the prediction
#   logic testable and reusable outside of the UI.
#
# FUNCTIONS IN THIS FILE:
#   1. load_xgboost_model(path)         -- Load the trained XGBoost model
#   2. load_rf_model(path)              -- Load the trained Random Forest model
#   3. load_codebert_components(...)    -- Load tokenizer + CodeBERT model
#   4. extract_codebert_embedding(...)  -- Run one function through CodeBERT
#   5. predict_with_model(...)          -- Full prediction pipeline
#   6. demo_predict(code)               -- Heuristic fallback when no model
# =============================================================================

import os
import numpy as np

# Import our utility functions from the same app/ directory
from utils import (
    extract_ast_features,
    extract_metric_features,
    build_feature_vector,
    get_verdict,
)


# ── SECTION 1: MODEL PATH RESOLUTION ─────────────────────────────────────────
#
# os.path.abspath(__file__) returns the full path of THIS script file.
# os.path.dirname(...)      returns the directory containing that file.
#
# This file lives at:  app/predictor.py
# So SCRIPT_DIR is:    .../MultiModal_Code_Vulnerability_Detection/app/
# PROJECT_ROOT is:     .../MultiModal_Code_Vulnerability_Detection/
# (one dirname() up from app/)

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)    # go one level up from app/
MODELS_DIR   = os.path.join(PROJECT_ROOT, "models")

# Expected model file paths (produced by src/model/train_classifier.py)
RF_MODEL_PATH  = os.path.join(MODELS_DIR, "random_forest.joblib")
XGB_MODEL_PATH = os.path.join(MODELS_DIR, "xgboost.json")


# ── FUNCTION 1: load_xgboost_model ───────────────────────────────────────────

def load_xgboost_model(path: str = XGB_MODEL_PATH):
    """
    Load the trained XGBoost classifier from its saved .json file.

    XGBoost uses its own save/load format (JSON), not Python's pickle.
    We must create an empty XGBClassifier and call .load_model() on it.

    Parameters:
        path (str): Full path to the xgboost.json file.

    Returns:
        XGBClassifier object if loading succeeds.
        None if the file does not exist or loading fails.
    """

    # Check if the file exists before trying to open it.
    # os.path.exists() returns True if the file is present on disk.
    if not os.path.exists(path):
        return None   # Signal to the app that no XGBoost model is available

    try:
        from xgboost import XGBClassifier   # import xgboost only when needed

        # Create an EMPTY XGBClassifier.
        # We set verbosity=0 to suppress all training/loading messages.
        model = XGBClassifier(verbosity=0)

        # Load the weights from the JSON file.
        # This fills the empty model with the saved tree structure and parameters.
        model.load_model(path)

        return model   # fully loaded model, ready to predict

    except Exception as e:
        # If any error occurs (import error, corrupted file, etc.), return None.
        # The app will fall back to demo mode.
        print(f"[predictor] Could not load XGBoost model: {e}")
        return None


# ── FUNCTION 2: load_rf_model ─────────────────────────────────────────────────

def load_rf_model(path: str = RF_MODEL_PATH):
    """
    Load the trained Random Forest classifier from its saved .joblib file.

    joblib is the standard serialisation (save/load) format for scikit-learn
    models. It stores the Python object in a compressed binary file.

    Parameters:
        path (str): Full path to the random_forest.joblib file.

    Returns:
        RandomForestClassifier object if loading succeeds.
        None if the file does not exist or loading fails.
    """

    if not os.path.exists(path):
        return None

    try:
        import joblib   # joblib is installed automatically with scikit-learn

        # joblib.load() reads the binary file and reconstructs the Python object.
        model = joblib.load(path)
        return model

    except Exception as e:
        print(f"[predictor] Could not load Random Forest model: {e}")
        return None


# ── FUNCTION 3: load_codebert_components ─────────────────────────────────────

def load_codebert_components():
    """
    Load the CodeBERT tokenizer and model from HuggingFace.

    WHAT HAPPENS HERE:
        1. The first time this runs, it downloads ~500 MB from HuggingFace.
        2. On subsequent runs, it loads from the local cache (~/.cache/huggingface/).
        3. model.eval() switches the model to "inference mode" (no gradient tracking).

    WHY @st.cache_resource (in app.py) IS IMPORTANT:
        Without caching, every time a user clicks "Analyze", Streamlit would
        re-run this function and reload 500 MB into memory. That would take
        60+ seconds per click. With caching, the model loads ONCE and stays
        in memory.

    Returns:
        (tokenizer, model): A tuple of the HuggingFace tokenizer and model objects.
                            Returns (None, None) if loading fails.
    """

    try:
        import torch
        from transformers import AutoTokenizer, AutoModel

        MODEL_NAME = "microsoft/codebert-base"

        # AutoTokenizer.from_pretrained() downloads (or loads from cache)
        # the BPE tokenizer used by CodeBERT.
        # The tokenizer converts text -> token IDs.
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

        # AutoModel.from_pretrained() downloads (or loads from cache)
        # the 125-million-parameter Transformer model weights.
        model = AutoModel.from_pretrained(MODEL_NAME)

        # model.eval() puts the model in evaluation mode.
        # This disables dropout layers (which add randomness during training)
        # so predictions are deterministic (same input -> same output).
        model.eval()

        return tokenizer, model

    except Exception as e:
        print(f"[predictor] Could not load CodeBERT: {e}")
        return None, None


# ── FUNCTION 4: extract_codebert_embedding ────────────────────────────────────

def extract_codebert_embedding(code: str, tokenizer, model) -> np.ndarray:
    """
    Run a C function through CodeBERT and return the [CLS] token embedding.

    WHAT IS THE [CLS] TOKEN?
        CodeBERT prepends a special token [CLS] (Classification) to every input.
        After the Transformer processes the input through 12 attention layers,
        the vector at position 0 (the [CLS] token) aggregates information from
        ALL other tokens via self-attention. It is used as the "sentence summary".

    WHAT WE EXTRACT:
        output.last_hidden_state has shape: (1, sequence_length, 768)
        We take [0, 0, :] to get: (768,) -- the [CLS] token at position 0.

    Parameters:
        code      (str): C function source code.
        tokenizer       : HuggingFace RobertaTokenizer.
        model           : HuggingFace AutoModel (CodeBERT weights).

    Returns:
        np.ndarray of shape (768,) -- the semantic embedding vector.
        Returns a zero vector of shape (768,) if inference fails.
    """

    try:
        import torch

        # ── Step 1: Tokenize ─────────────────────────────────────────────────
        #
        # tokenizer() converts the code string into:
        #   input_ids      : integer IDs for each token (tensor shape: 1 x 512)
        #   attention_mask : 1 for real tokens, 0 for padding (tensor shape: 1 x 512)
        #
        # return_tensors="pt"   -- return PyTorch tensors (not lists)
        # max_length=512        -- truncate to 512 tokens (CodeBERT's limit)
        # truncation=True       -- enable truncation if code > 512 tokens
        # padding="max_length"  -- pad shorter code to exactly 512 tokens

        inputs = tokenizer(
            code,
            return_tensors="pt",
            max_length=512,
            truncation=True,
            padding="max_length",
        )

        # ── Step 2: Run CodeBERT ─────────────────────────────────────────────
        #
        # torch.no_grad() disables gradient computation.
        # During training, PyTorch tracks gradients for backpropagation.
        # During inference, we DON'T need gradients -- disabling them:
        #   - Reduces memory usage by ~50%
        #   - Speeds up the forward pass
        #
        # model(**inputs) unpacks the dict returned by the tokenizer.
        # It is equivalent to: model(input_ids=..., attention_mask=...)

        with torch.no_grad():
            output = model(**inputs)

        # ── Step 3: Extract [CLS] token ──────────────────────────────────────
        #
        # output.last_hidden_state has shape: (batch_size=1, seq_len=512, hidden=768)
        # [0, 0, :] selects:
        #   [0]  -- first (and only) item in the batch
        #   [0]  -- first token position ([CLS] token)
        #   [:]  -- all 768 dimensions

        cls_embedding = output.last_hidden_state[0, 0, :]

        # .numpy() converts the PyTorch tensor to a numpy array.
        # .cpu() ensures it is on CPU memory (not GPU), which numpy requires.
        return cls_embedding.cpu().numpy()   # shape: (768,)

    except Exception as e:
        print(f"[predictor] CodeBERT inference failed: {e}")
        # Return a zero vector as fallback so the rest of the pipeline continues
        return np.zeros(768, dtype=np.float64)


# ── FUNCTION 5: predict_with_model ───────────────────────────────────────────

def predict_with_model(code: str, model, model_name: str,
                        tokenizer, codebert_model) -> dict:
    """
    Full prediction pipeline for a single C function:
        1. Extract AST features (11 dims)
        2. Extract software metrics (13 dims)
        3. Extract CodeBERT embedding (768 dims)
        4. Concatenate into 792-dim feature vector
        5. Run the trained classifier
        6. Return verdict dictionary

    Parameters:
        code          (str):  C source code to analyse.
        model               : Loaded XGBoost or Random Forest model.
        model_name    (str):  Display name e.g. "XGBoost".
        tokenizer           : HuggingFace tokenizer (or None if unavailable).
        codebert_model      : HuggingFace CodeBERT model (or None if unavailable).

    Returns:
        dict from get_verdict() plus raw feature values for display.
    """

    # ── Step 1: Extract AST features ─────────────────────────────────────────
    ast_feats    = extract_ast_features(code)

    # ── Step 2: Extract software metrics ─────────────────────────────────────
    metric_feats = extract_metric_features(code)

    # ── Step 3: Extract CodeBERT embedding ───────────────────────────────────
    if tokenizer is not None and codebert_model is not None:
        # Real CodeBERT embedding
        embedding = extract_codebert_embedding(code, tokenizer, codebert_model)
        embedding_source = "CodeBERT (microsoft/codebert-base)"
    else:
        # Fallback: zero embedding if CodeBERT is not available.
        # The model was trained with real embeddings, so predictions will be
        # less accurate, but the pipeline still produces an output.
        embedding = np.zeros(768, dtype=np.float64)
        embedding_source = "Zero vector (CodeBERT not loaded)"

    # ── Step 4: Assemble 792-dim feature vector ───────────────────────────────
    feature_vector = build_feature_vector(ast_feats, metric_feats, embedding)

    # reshape(1, -1) converts shape (792,) to (1, 792).
    # Scikit-learn/XGBoost expect 2D input: [n_samples, n_features].
    # Here n_samples = 1 (one function at a time).
    X = feature_vector.reshape(1, -1)   # shape: (1, 792)

    # ── Step 5: Run the classifier ────────────────────────────────────────────
    #
    # predict() returns the class label: 0 (safe) or 1 (vulnerable).
    # predict_proba() returns a probability array: [[prob_safe, prob_vuln]]
    # We take [0, 1] to get the probability of being vulnerable.

    prediction       = int(model.predict(X)[0])          # 0 or 1
    probabilities    = model.predict_proba(X)[0]          # [prob_0, prob_1]
    vuln_probability = float(probabilities[1])            # probability of class 1

    # ── Step 6: Build verdict dictionary ─────────────────────────────────────
    result = get_verdict(prediction, vuln_probability, model_name)

    # Attach the raw feature breakdowns so the UI can display them
    result["ast_features"]    = ast_feats
    result["metric_features"] = metric_feats
    result["embedding_dims"]  = int(embedding.shape[0])   # should be 768
    result["embedding_source"]= embedding_source
    result["feature_vector_shape"] = X.shape              # (1, 792)

    return result


# ── FUNCTION 6: demo_predict ─────────────────────────────────────────────────

def demo_predict(code: str) -> dict:
    """
    DEMO MODE: A simple rule-based heuristic prediction used when
    the trained models (XGBoost, Random Forest) are not available.

    This is NOT machine learning. It uses simple threshold rules on a
    few key features to produce an illustrative prediction.

    The UI clearly labels results as "DEMO MODE" so the user understands
    this is a fallback, not the real trained model.

    Parameters:
        code (str): C source code string.

    Returns:
        dict matching the structure returned by predict_with_model()
    """

    ast_feats    = extract_ast_features(code)
    metric_feats = extract_metric_features(code)

    # ── Simple risk score based on top features from our importance analysis ──
    #
    # From our model's feature importance (see results/07_feature_importance.png):
    # The top predictors were: n_pointer_ops, pointer_count, n_loops, nesting_depth
    #
    # We build a simple weighted score:

    score = 0.0

    n_ptr    = ast_feats.get("n_pointer_ops", 0)
    ptr_cnt  = metric_feats.get("pointer_count", 0)
    n_loops  = ast_feats.get("n_loops", 0)
    depth    = metric_feats.get("nesting_depth", 0)
    loc      = metric_feats.get("loc", 0)
    n_calls  = ast_feats.get("n_function_calls", 0)
    n_err    = ast_feats.get("n_error_nodes", 0)

    # Weights are proportional to feature importance rank
    score += min(n_ptr   / 10.0, 1.0) * 0.30   # pointer ops   (rank 1)
    score += min(ptr_cnt / 15.0, 1.0) * 0.25   # pointer count (rank 2)
    score += min(n_loops / 5.0,  1.0) * 0.15   # loops         (rank 3)
    score += min(depth   / 6.0,  1.0) * 0.12   # nesting depth (rank 4)
    score += min(loc     / 80.0, 1.0) * 0.10   # lines of code (rank 10)
    score += min(n_calls / 8.0,  1.0) * 0.05   # function calls(rank 8)
    score += min(n_err   / 2.0,  1.0) * 0.03   # parse errors

    # Clamp to [0.05, 0.95] -- never be 100% certain in demo mode
    vuln_probability = max(0.05, min(0.95, score))

    # Use 0.5 as the decision threshold (same as our trained model)
    prediction = 1 if vuln_probability >= 0.5 else 0

    result = get_verdict(prediction, vuln_probability, "Demo Heuristic (no model loaded)")
    result["ast_features"]     = ast_feats
    result["metric_features"]  = metric_feats
    result["embedding_dims"]   = 0
    result["embedding_source"] = "Not used in demo mode"
    result["feature_vector_shape"] = (1, 24)   # only AST + metrics in demo
    result["is_demo"]          = True          # flag so UI can show warning

    return result
