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

import logging
import os
import numpy as np

# Import our utility functions from the same app/ directory
from utils import (
    extract_ast_features,
    extract_metric_features,
    build_feature_vector,
    get_verdict,
)

logger = logging.getLogger(__name__)


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

# Decision threshold for the binary VULNERABLE/NOT VULNERABLE verdict.
#
# RE-SELECTED after the Phase 4 feature-fusion alignment fix
# (docs/ML_FORENSIC_AUDIT_PHASE4.md) -- the dataset used to select the
# previous value (0.32) was corrupted (99.35% of rows paired the wrong
# function's CodeBERT/metrics features with the label/AST features), so
# that number is INVALIDATED, not merely superseded. This is a fresh
# result on the corrected dataset, not a tweak of the old one.
#
# Same methodology as before (train/validation/test split, test set
# touched exactly once at the end) -- see docs/ML_EXPERIMENTS.md
# Experiment 1. On the corrected data: F1 0.5315 -> 0.6361 relative to the
# naive default of 0.5, trading precision (54.5% -> 47.2%) for a much
# higher recall (51.8% -> 97.7%) -- an even more aggressive
# recall-favoring operating point than the old (invalidated) 0.32 value.
VULNERABILITY_THRESHOLD = 0.26


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
        logger.warning("Could not load XGBoost model: %s", e)
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
        logger.warning("Could not load Random Forest model: %s", e)
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
        logger.warning("Could not load CodeBERT: %s", e)
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
        logger.warning("CodeBERT inference failed: %s", e)
        # Return a zero vector as fallback so the rest of the pipeline continues
        return np.zeros(768, dtype=np.float64)


# ── FUNCTION 4b: extract_codebert_embeddings_batch ───────────────────────────
#
# Per-function live inference (docs/PER_FUNCTION_INFERENCE_DESIGN.md) needs
# one CodeBERT embedding per function in a scanned file, not one per file --
# a real repo can have 5-15x more functions than files (measured on real
# repos: zlib 5.4, mbedTLS 8.9, libpng 14.5 functions/file). Calling
# extract_codebert_embedding() once per function sequentially would make
# batch/GitHub scans of real repos impractically slow. This batches multiple
# functions into ONE tokenizer call + ONE forward pass instead, in chunks
# (BATCH_SIZE) so a single pathological file with hundreds of functions
# can't spike memory in one shot.

BATCH_SIZE = 16


def extract_codebert_embeddings_batch(codes: list, tokenizer, model, batch_size: int = BATCH_SIZE) -> np.ndarray:
    """
    Same tokenization settings as extract_codebert_embedding (max_length=512,
    truncation=True, padding="max_length") applied to a LIST of code strings
    in batched forward pass(es) instead of one call per string.

    Parameters:
        codes  (list[str]): one code string per item to embed (e.g. one per
                             function in a scanned file).
        batch_size   (int): how many items to tokenize/run together per
                             forward pass. Chunks `codes` into groups of at
                             most this size rather than one single batch, so
                             a file with an unusually large number of
                             functions can't spike memory in one shot.

    Returns:
        np.ndarray of shape (len(codes), 768), one row per input, in the
        same order. If a chunk's forward pass fails, that chunk's rows are
        zero vectors (matching extract_codebert_embedding's single-item
        fallback behavior) rather than failing every function's result.
    """
    if not codes:
        return np.zeros((0, 768), dtype=np.float64)

    chunks = []
    for start in range(0, len(codes), batch_size):
        chunk = codes[start:start + batch_size]
        try:
            import torch

            # padding=True (pad to the longest item IN THIS CHUNK) instead of
            # padding="max_length" (pad every item to a full 512 regardless
            # of actual length) -- docs/ASYNC_SCAN_DESIGN.md Sec 4: the
            # median function is ~260 of 512 tokens
            # (docs/PER_FUNCTION_INFERENCE_DESIGN.md), so roughly half of
            # every chunk's compute was spent on padding tokens that
            # contribute nothing (the attention mask already excludes them
            # from the [CLS] output either way). Verified numerically
            # equivalent to padding="max_length" before this change shipped
            # -- src/model/verify_dynamic_padding.py, run against this exact
            # function, unmodified: max abs diff 0.0 for batches containing
            # a truncated (512-token) item, ~1e-6 (float32 precision noise,
            # not a systematic difference) for all-short batches, both well
            # under the 1e-5 tolerance used to judge equivalence.
            inputs = tokenizer(
                chunk,
                return_tensors="pt",
                max_length=512,
                truncation=True,
                padding=True,
            )
            with torch.no_grad():
                output = model(**inputs)
            # output.last_hidden_state shape: (batch, seq_len, 768).
            # [:, 0, :] takes the [CLS] token for every item in the batch at once.
            cls_embeddings = output.last_hidden_state[:, 0, :].cpu().numpy()
            chunks.append(cls_embeddings)
        except Exception as e:
            logger.warning("Batched CodeBERT inference failed for a chunk of %d function(s): %s", len(chunk), e)
            chunks.append(np.zeros((len(chunk), 768), dtype=np.float64))

    return np.vstack(chunks)


# ── FUNCTION 4c: predict_functions_with_model ────────────────────────────────

def predict_functions_with_model(functions: list, model, model_name: str,
                                  tokenizer, codebert_model) -> list:
    """
    Runs the full prediction pipeline (AST + metrics + CodeBERT -> 792-dim
    vector -> trained classifier) independently for each function in
    `functions`, the same per-item logic predict_with_model() uses for a
    single whole input -- but with CodeBERT embeddings computed in batched
    forward pass(es) via extract_codebert_embeddings_batch() rather than one
    call per function.

    Parameters:
        functions (list[dict]): each dict must have a "text" key (the
            function's source). Any other keys (e.g. "name", "start_line",
            "end_line") are carried through into that function's result
            unchanged -- this function doesn't need to know what they mean.
        model, model_name, tokenizer, codebert_model: same as predict_with_model.

    Returns:
        list[dict], one verdict dict per function (same shape get_verdict()
        produces, plus ast_features/metric_features/embedding_dims and every
        extra key the input dict carried), in the same order as `functions`.
    """
    texts = [f["text"] for f in functions]
    if tokenizer is not None and codebert_model is not None:
        embeddings = extract_codebert_embeddings_batch(texts, tokenizer, codebert_model)
    else:
        embeddings = np.zeros((len(functions), 768), dtype=np.float64)

    results = []
    for fn, embedding in zip(functions, embeddings):
        ast_feats = extract_ast_features(fn["text"])
        metric_feats = extract_metric_features(fn["text"])
        feature_vector = build_feature_vector(ast_feats, metric_feats, embedding)
        X = feature_vector.reshape(1, -1)

        probabilities = model.predict_proba(X)[0]
        vuln_probability = float(probabilities[1])
        prediction = int(vuln_probability >= VULNERABILITY_THRESHOLD)

        result = get_verdict(prediction, vuln_probability, model_name)
        for key, value in fn.items():
            if key != "text":
                result[key] = value
        result["ast_features"] = ast_feats
        result["metric_features"] = metric_feats
        result["embedding_dims"] = int(embedding.shape[0])
        # Internal-only (leading underscore, never serialized -- no API
        # response spreads this dict, confirmed by grep before this change
        # shipped): the raw 768-dim CodeBERT embedding already computed
        # above, carried through so callers (scan_service.py's PCA-scatter
        # projection) can reuse it instead of paying for a second forward
        # pass over the same code just to get the same vector again. See
        # docs/ASYNC_SCAN_DESIGN.md Sec 4 / Phase F.
        result["_embedding"] = embedding
        results.append(result)

    return results


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
    # predict_proba() returns a probability array: [[prob_safe, prob_vuln]].
    # The class label is derived from VULNERABILITY_THRESHOLD (see above),
    # not from model.predict()'s implicit, untuned 0.5 cutoff.

    probabilities    = model.predict_proba(X)[0]          # [prob_0, prob_1]
    vuln_probability = float(probabilities[1])            # probability of class 1
    prediction       = int(vuln_probability >= VULNERABILITY_THRESHOLD)  # 0 or 1

    # ── Step 6: Build verdict dictionary ─────────────────────────────────────
    result = get_verdict(prediction, vuln_probability, model_name)

    # Attach the raw feature breakdowns so the UI can display them
    result["ast_features"]    = ast_feats
    result["metric_features"] = metric_feats
    result["embedding_dims"]  = int(embedding.shape[0])   # should be 768
    result["embedding_source"]= embedding_source
    result["feature_vector_shape"] = X.shape              # (1, 792)
    # Internal-only, not serialized anywhere -- see the matching comment in
    # predict_functions_with_model() above.
    result["_embedding"] = embedding

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
