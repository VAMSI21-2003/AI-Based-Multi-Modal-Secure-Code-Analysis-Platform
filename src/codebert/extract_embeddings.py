# =============================================================================
# extract_embeddings.py
# Day 7: CodeBERT Embedding Extraction
# Project: Multi-Modal Code Vulnerability Detection Using CodeBERT
# =============================================================================
#
# ── WHAT IS CodeBERT? ────────────────────────────────────────────────────────
#
#   CodeBERT is a pretrained AI model released by Microsoft Research in 2020.
#   It was trained on 8.35 million code-comment pairs from GitHub across
#   6 programming languages: Python, Java, JavaScript, PHP, Ruby, and Go.
#   Later versions also support C/C++.
#
#   Think of it like this:
#     - A dictionary gives you the MEANING of a word.
#     - CodeBERT gives you the MEANING of a piece of source code.
#
#   It does this by converting code into a 768-number list called an EMBEDDING.
#   Two code snippets that do similar things produce SIMILAR embedding vectors,
#   even if they look very different as text.
#
# ── WHAT IS AN EMBEDDING? ────────────────────────────────────────────────────
#
#   An embedding is a fixed-size list of floating-point numbers that represents
#   the MEANING of something (a word, a sentence, or a code function).
#
#   Example: CodeBERT converts:
#     "for (i=0; i<n; i++) { buf[i]=src[i]; }"
#   into:
#     [0.1823, -0.4521, 0.0034, 0.7821, ..., -0.2341]   (768 numbers total)
#
#   These 768 numbers capture:
#     - What operations the code performs
#     - What variables are used
#     - The overall structure and intent of the code
#
#   The embedding is like a "fingerprint" of the code's meaning.
#   Similar code → similar fingerprint.
#   Vulnerable patterns → fingerprints clustered together in 768-D space.
#
# ── THE [CLS] TOKEN ──────────────────────────────────────────────────────────
#
#   When CodeBERT processes code, it prepends a special token: [CLS]
#   (short for CLaSsification). This token has no meaning of its own —
#   the model is trained to put a SUMMARY of the entire input into
#   the [CLS] position's output vector. So we take the [CLS] output
#   (768 numbers) as the "embedding of the whole function."
#
# ── WHAT THIS SCRIPT DOES ────────────────────────────────────────────────────
#
#   STEP 1  : Detect whether a GPU is available (faster) or use CPU
#   STEP 2  : Download and load CodeBERT tokenizer
#   STEP 3  : Download and load CodeBERT model weights
#   STEP 4  : Demo on 2 hand-written C samples (no dataset needed)
#   STEP 5  : Load the cleaned Devign dataset
#   STEP 6  : Extract embeddings in batches (efficient processing)
#   STEP 7  : Save embeddings as CSV and NumPy array
#   STEP 8  : Print statistics
#
# ── HOW TO RUN ───────────────────────────────────────────────────────────────
#
#   1. Open VS Code terminal         (Ctrl + backtick)
#   2. Activate venv:                .\venv\Scripts\activate
#   3. Navigate here:                cd src\codebert
#   4. Run:                          python extract_embeddings.py
#
#   FIRST RUN: CodeBERT model files (~500 MB) will be downloaded automatically
#   from HuggingFace Hub. This requires an internet connection and may take
#   5-10 minutes depending on your connection speed.
#   Subsequent runs load from local cache (fast).
#
# ── TIME ESTIMATE ─────────────────────────────────────────────────────────────
#
#   CPU (your laptop):  ~10 seconds per 10 samples  -> ~7-8 hours for 27,231 samples
#   GPU (Google Colab): ~2 seconds per 100 samples  -> ~10-15 minutes for 27,231 samples
#
#   This script processes the FULL dataset by default (MAX_SAMPLES = None).
#   Set MAX_SAMPLES to a small integer (e.g., 200) if you want a quick local
#   smoke test before committing to a full run.
# =============================================================================


# ── SECTION 0: IMPORTS ────────────────────────────────────────────────────────
#
# os, sys  : file paths and exit
# numpy    : numerical arrays (np.save / np.load for efficient storage)
# pandas   : tabular data (CSV loading and saving)
# torch    : PyTorch — the deep learning framework CodeBERT runs on
# transformers : HuggingFace library — loads CodeBERT tokenizer and model

import os

# Must be set BEFORE `transformers` (and therefore the Rust `tokenizers`
# package) is imported. HuggingFace's fast tokenizer runs its own internal
# thread pool for batch tokenization; left enabled, that pool can contend
# with PyTorch's own CPU thread pool over a long run (thousands of batches)
# and has been observed to crash the process natively on Windows with no
# Python-level traceback (SIGSEGV / exit 139). Disabling it trades a small
# amount of tokenization speed for run stability, which matters far more
# over a multi-hour full-dataset extraction.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import sys
import gc
import json
import time
import numpy as np
import pandas as pd

try:
    import torch
except ImportError:
    print("ERROR: PyTorch is not installed.")
    print("Run: pip install torch")
    sys.exit(1)

try:
    from transformers import AutoTokenizer, AutoModel
except ImportError:
    print("ERROR: HuggingFace Transformers is not installed.")
    print("Run: pip install transformers")
    sys.exit(1)


# ── SECTION 1: CONSTANTS ──────────────────────────────────────────────────────

# The official HuggingFace model ID for CodeBERT.
# AutoTokenizer and AutoModel will automatically download this model
# on first run and cache it locally.
MODEL_NAME = "microsoft/codebert-base"

# CodeBERT processes at most 512 tokens at a time (its architectural limit).
# Code functions longer than this will be TRUNCATED — the beginning is kept
# and the end is cut off. For Devign, average functions are ~200-300 tokens,
# so most will fit without truncation.
MAX_LENGTH = 512

# BATCH_SIZE controls how many code samples are processed at one time.
# Larger batch = faster, but uses more RAM/VRAM.
# 16 is safe for CPU with 8GB RAM; reduce to 8 if you run out of memory.
# On a GPU (e.g. Google Colab), there is much more memory available, so we
# use a larger batch size automatically to speed up the full-dataset run.
BATCH_SIZE = 32 if torch.cuda.is_available() else 16

# MAX_SAMPLES: how many Devign samples to process in this run.
#   None = process ALL samples (default -- required for the full dataset).
#   Set to a small integer (e.g., 200) only for a quick local smoke test.
MAX_SAMPLES = None

# How often (in batches) to print a full progress update with ETA.
# The dataset has thousands of batches, so printing every single one would
# flood the terminal -- we print a detailed line every PROGRESS_EVERY batches.
PROGRESS_EVERY = 10

# How often (in batches) to write a resumable checkpoint to disk.
# A full CPU run takes hours; if the process is interrupted or crashes
# (e.g. an OS-level fault unrelated to our code), we do not want to lose
# all progress and start over from sample 0. Every CHECKPOINT_EVERY batches
# we save what has been computed so far -- the next run picks up where
# this one left off instead of repeating already-finished work.
CHECKPOINT_EVERY = 100

# The dimensionality of CodeBERT's output embedding.
# Every function produces exactly 768 numbers regardless of how long it is.
EMBEDDING_DIM = 768


# ── SECTION 2: PATH SETUP ─────────────────────────────────────────────────────
#
# Build all paths from this script's own location so the script works
# regardless of what directory you run it from.

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

PROCESSED_DIR = os.path.join(PROJECT_ROOT, "dataset", "processed")
NOTES_DIR     = os.path.join(PROJECT_ROOT, "dataset", "notes")

# We try to load the fully cleaned CSV from Day 4.
# If not found, we try the raw function.json from Day 3.
INPUT_CSV   = os.path.join(PROCESSED_DIR, "devign_cleaned.csv")
INPUT_JSON  = os.path.join(PROJECT_ROOT,  "dataset", "raw", "function.json")

# Output files:
#   CSV  — human-readable, compatible with pandas
#   NPY  — numpy binary format (smaller, faster to load)
OUTPUT_CSV = os.path.join(PROCESSED_DIR, "codebert_embeddings.csv")
OUTPUT_NPY = os.path.join(PROCESSED_DIR, "codebert_embeddings.npy")
OUTPUT_META_CSV = os.path.join(PROCESSED_DIR, "codebert_metadata.csv")

# Resumable checkpoint files (deleted automatically on successful completion).
# Kept separate from the final OUTPUT_* files so a partial/interrupted run
# never gets mistaken for a finished one.
CHECKPOINT_NPY  = os.path.join(PROCESSED_DIR, "codebert_embeddings_checkpoint.npy")
CHECKPOINT_META = os.path.join(PROCESSED_DIR, "codebert_embeddings_checkpoint.json")


# ── UTILITY ───────────────────────────────────────────────────────────────────

def section(title):
    """Prints a visible header bar to organise terminal output."""
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


# ── SECTION 3: DEVICE DETECTION ───────────────────────────────────────────────
#
# A "device" in PyTorch is where computations happen:
#   "cuda"  = NVIDIA GPU (much faster for large models)
#   "cpu"   = your processor (slower but always available)
#
# torch.cuda.is_available() returns True if an NVIDIA GPU is detected.
# We use GPU if available, otherwise fall back to CPU automatically.

section("STEP 1: DETECTING COMPUTE DEVICE")

if torch.cuda.is_available():
    DEVICE = torch.device("cuda")
    device_name = torch.cuda.get_device_name(0)
    print(f"  GPU detected: {device_name}")
    print(f"  Using device: cuda  (fast — GPU processing)")
else:
    DEVICE = torch.device("cpu")
    print(f"  No GPU detected.")
    print(f"  Using device: cpu  (slower — CPU processing)")
    print(f"  Tip: Run on Google Colab for free GPU access.")

print(f"  PyTorch version       : {torch.__version__}")
print(f"  Batch size            : {BATCH_SIZE}")
print(f"  Max samples this run  : {MAX_SAMPLES if MAX_SAMPLES else 'ALL'}")


# ── SECTION 4: LOAD TOKENIZER ─────────────────────────────────────────────────
#
# The TOKENIZER is the first stage of CodeBERT processing.
#
# What a tokenizer does:
#   1. Splits code into small pieces called "tokens"
#      Example: "uint8_t buf[1024];" becomes
#               ["uint", "8", "_", "t", "Ġbuf", "[", "1024", "]", ";"]
#      (Ġ means there was a space before this token)
#
#   2. Converts each token into a unique integer ID
#      Example: ["uint", "8", ...] → [16791, 290, ...]
#
#   3. Adds special tokens:
#      [CLS] at the beginning  (ID = 0)
#      [SEP] at the end        (ID = 2)
#      [PAD] for padding       (ID = 1)
#
#   After tokenization, the model receives a list of integer IDs.
#
# AutoTokenizer.from_pretrained(MODEL_NAME):
#   - First run: downloads tokenizer files from HuggingFace (~1 MB)
#   - Subsequent runs: loads from local cache at ~/.cache/huggingface/

section("STEP 2: LOADING CODEBERT TOKENIZER")

print(f"  Model: {MODEL_NAME}")
print(f"  Downloading tokenizer (first run only)...")

try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    print(f"  Tokenizer loaded successfully.")
    print(f"  Vocabulary size: {tokenizer.vocab_size:,} tokens")
    print(f"  Max token length: {MAX_LENGTH}")
except Exception as e:
    print(f"  ERROR loading tokenizer: {e}")
    print(f"  Check your internet connection and try again.")
    sys.exit(1)


# ── SECTION 5: LOAD CODEBERT MODEL ────────────────────────────────────────────
#
# The MODEL is a neural network with 125 million parameters.
# It was pretrained on millions of code files to learn code semantics.
#
# AutoModel.from_pretrained(MODEL_NAME):
#   - First run: downloads model weights from HuggingFace (~500 MB)
#   - Subsequent runs: loads from local cache (takes a few seconds)
#
# model.eval():
#   Puts the model in EVALUATION mode (as opposed to training mode).
#   In eval mode:
#     - Dropout layers are disabled (they randomly drop neurons during training
#       to prevent overfitting, but we don't want that during inference)
#     - BatchNorm layers use fixed statistics
#   This is REQUIRED whenever you use a model for prediction/embedding, not training.
#
# model.to(DEVICE):
#   Moves all model parameters to the selected device (GPU or CPU).
#   The input data must later be moved to the same device.

section("STEP 3: LOADING CODEBERT MODEL")

print(f"  Loading model weights (~500 MB download on first run)...")
print(f"  Please wait...")

try:
    model = AutoModel.from_pretrained(MODEL_NAME)
    model.eval()        # switch to evaluation (inference) mode
    model.to(DEVICE)    # move to GPU or CPU

    # Count parameters to give the user a sense of model size
    total_params = sum(p.numel() for p in model.parameters())
    print(f"  Model loaded successfully.")
    print(f"  Total parameters: {total_params:,}  (~125 million)")
    print(f"  Model moved to  : {DEVICE}")
except Exception as e:
    print(f"  ERROR loading model: {e}")
    sys.exit(1)


# ── SECTION 6: DEFINE EMBEDDING EXTRACTION FUNCTIONS ─────────────────────────


def tokenize_code(code_string, max_length=MAX_LENGTH):
    """
    Convert one C code string into tokenized input tensors for CodeBERT.

    This function handles:
      - Splitting code into tokens
      - Converting tokens to integer IDs
      - Adding [CLS] and [SEP] special tokens
      - Padding to max_length (so all inputs have the same size)
      - Truncating if longer than max_length

    Parameters:
        code_string (str)  : the raw C source code
        max_length  (int)  : maximum number of tokens (default 512)

    Returns:
        dict containing:
            input_ids      : tensor of shape (1, max_length) — token IDs
            attention_mask : tensor of shape (1, max_length) — 1=real token, 0=padding
    """
    # tokenizer() call:
    #   return_tensors="pt"   → return PyTorch tensors (not Python lists)
    #   max_length            → enforce the 512-token limit
    #   truncation=True       → if code has >512 tokens, cut the end off
    #   padding="max_length"  → if code has <512 tokens, pad with [PAD] tokens
    encoded = tokenizer(
        code_string,
        return_tensors="pt",
        max_length=max_length,
        truncation=True,
        padding="max_length",
    )
    return encoded


def extract_single_embedding(code_string):
    """
    Extract a CodeBERT embedding for ONE code function.

    Steps:
      1. Tokenize the code string
      2. Move tokens to the compute device (GPU/CPU)
      3. Pass tokens through CodeBERT
      4. Extract the [CLS] token output (position 0)
      5. Move result back to CPU and convert to numpy

    Parameters:
        code_string (str) : C source code of one function

    Returns:
        numpy array of shape (768,) — the embedding vector
    """

    # Tokenize
    encoded = tokenize_code(code_string)

    # Move to device: every tensor must live on the same device as the model
    # {k: v.to(DEVICE) for k, v in encoded.items()} is a dictionary
    # comprehension — it creates a new dict with each tensor moved to DEVICE
    encoded = {key: value.to(DEVICE) for key, value in encoded.items()}

    # Forward pass through CodeBERT
    # torch.no_grad() is a context manager that tells PyTorch:
    #   "Do NOT track gradients for these operations."
    # During training, gradients are needed to update model weights.
    # During inference (embedding extraction), we are NOT training —
    # so tracking gradients wastes memory and time.
    with torch.no_grad():
        output = model(**encoded)
        # **encoded unpacks the dict as keyword arguments:
        # equivalent to model(input_ids=..., attention_mask=...)

    # output.last_hidden_state has shape: (batch=1, seq_len=512, hidden_dim=768)
    # Explanation of dimensions:
    #   batch=1        : we processed 1 sample
    #   seq_len=512    : 512 tokens (padded/truncated to MAX_LENGTH)
    #   hidden_dim=768 : CodeBERT's internal representation size
    #
    # We want position 0 (the [CLS] token) for all 768 hidden dimensions:
    #   [0, 0, :]  means:  batch index 0, token position 0, all 768 values
    cls_embedding = output.last_hidden_state[0, 0, :]   # shape: (768,)

    # .cpu()     → move tensor from GPU to CPU (harmless if already on CPU)
    # .numpy()   → convert PyTorch tensor to NumPy array
    return cls_embedding.cpu().numpy()


def extract_batch_embeddings(code_list):
    """
    Extract CodeBERT embeddings for a LIST of code strings at once.

    Processing multiple samples together (a "batch") is much faster than
    calling extract_single_embedding() in a loop, because the GPU/CPU
    can work on them in parallel.

    Parameters:
        code_list (list of str) : multiple C source code strings

    Returns:
        numpy array of shape (len(code_list), 768)
    """

    # Tokenize all samples in the list together.
    # padding=True pads each sequence to the length of the longest one
    # in THIS batch (not to max_length), which is slightly more efficient.
    encoded = tokenizer(
        code_list,
        return_tensors="pt",
        max_length=MAX_LENGTH,
        truncation=True,
        padding=True,
    )

    # Move all tensors in the batch to the compute device
    encoded = {key: value.to(DEVICE) for key, value in encoded.items()}

    # torch.no_grad(): no gradients are tracked, so PyTorch does not keep
    # the activation history it would normally need for backpropagation.
    # This is what keeps memory usage flat, batch after batch.
    with torch.no_grad():
        output = model(**encoded)

        # output.last_hidden_state shape: (batch_size, seq_len, 768)
        # [:, 0, :] means:
        #   :       → all samples in the batch
        #   0       → position 0 (the [CLS] token)
        #   :       → all 768 dimensions
        # .detach()   → cut the tensor off from the computation graph
        # .cpu()      → move the result off the GPU immediately
        # .numpy()    → convert to a plain NumPy array
        cls_embeddings = output.last_hidden_state[:, 0, :].detach().cpu().numpy()

    # ── Free memory immediately ───────────────────────────────────────────────
    # Explicitly delete the large GPU/CPU tensors for this batch instead of
    # waiting for Python's garbage collector to get around to it, and release
    # any cached GPU memory back to the driver so it can be reused by the
    # next batch. This is what allows the script to process tens of
    # thousands of samples without memory usage growing over time.
    del encoded, output
    if DEVICE.type == "cuda":
        torch.cuda.empty_cache()

    return cls_embeddings


# ── SECTION 7: DEMO ON TWO HAND-WRITTEN C FUNCTIONS ──────────────────────────
#
# We demonstrate embedding extraction on two functions before touching the
# full dataset. This confirms the setup works and teaches what embeddings
# look like.

section("STEP 4: DEMO -- EXTRACTING EMBEDDINGS FROM SAMPLE C FUNCTIONS")

DEMO_SAMPLES = [
    {
        "name"   : "VULNERABLE (label=1) -- Buffer Overflow",
        "label"  : 1,
        "code"   : """\
static int hq_decode(const uint8_t *src, int src_size, uint8_t *dst) {
    uint8_t buf[1024];
    int i;
    if (src_size <= 0) return -1;
    for (i = 0; i < src_size; i++) {
        buf[i] = src[i];
    }
    return copy_out(buf, dst);
}""",
    },
    {
        "name"   : "NON-VULNERABLE (label=0) -- Safe Version",
        "label"  : 0,
        "code"   : """\
static int hq_decode(const uint8_t *src, int src_size, uint8_t *dst) {
    uint8_t buf[1024];
    int i;
    if (src_size <= 0 || src_size > (int)sizeof(buf)) return -1;
    for (i = 0; i < src_size; i++) {
        buf[i] = src[i];
    }
    return copy_out(buf, dst);
}""",
    },
]

demo_embeddings = []

for sample in DEMO_SAMPLES:
    print()
    print(f"  Processing: {sample['name']}")

    emb = extract_single_embedding(sample["code"])
    demo_embeddings.append(emb)

    print(f"  Embedding shape       : {emb.shape}  (768 numbers)")
    print(f"  First 8 values        : {emb[:8].round(4).tolist()}")
    print(f"  Last 8 values         : {emb[-8:].round(4).tolist()}")
    print(f"  Min value             : {emb.min():.4f}")
    print(f"  Max value             : {emb.max():.4f}")
    print(f"  Mean value            : {emb.mean():.4f}")
    print(f"  Non-zero dimensions   : {np.count_nonzero(emb)} / 768")

# ── Cosine similarity between the two demo embeddings ────────────────────────
#
# Cosine similarity measures how similar two vectors are in direction.
# Range: -1 (opposite) to +1 (identical).
# Two code functions that do the same thing should have HIGH similarity.

emb_vuln = demo_embeddings[0]
emb_safe = demo_embeddings[1]

# Dot product of unit vectors = cosine similarity
norm_v   = np.linalg.norm(emb_vuln)   # length (magnitude) of vector 1
norm_s   = np.linalg.norm(emb_safe)   # length (magnitude) of vector 2
cos_sim  = np.dot(emb_vuln, emb_safe) / (norm_v * norm_s)

print()
print(f"  ---- SIMILARITY BETWEEN THE TWO SAMPLES ----")
print(f"  Cosine similarity: {cos_sim:.4f}")
print(f"  (Range: 0.0 = completely different, 1.0 = identical)")
print()
print("  INTERPRETATION:")
if cos_sim > 0.95:
    print("  Very high similarity — CodeBERT recognises these two functions")
    print("  as structurally and semantically near-identical.")
    print("  The tiny difference (the missing bounds check) may not be")
    print("  enough on its own — this is why we also use AST + Metrics.")
elif cos_sim > 0.80:
    print("  High similarity — CodeBERT sees these as related functions.")
elif cos_sim > 0.60:
    print("  Moderate similarity — CodeBERT detects meaningful differences.")
else:
    print("  Low similarity — CodeBERT sees these as quite different functions.")


# ── SECTION 8: LOAD THE DEVIGN DATASET ───────────────────────────────────────

section("STEP 5: LOADING DEVIGN DATASET")

df = None

# Try the cleaned CSV from Day 4 first
if os.path.exists(INPUT_CSV):
    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    print(f"  Loaded (cleaned CSV) : {INPUT_CSV}")

# Fall back to the raw JSON if CSV not found
elif os.path.exists(INPUT_JSON):
    import json
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)
    df = pd.DataFrame(raw)
    print(f"  Loaded (raw JSON)    : {INPUT_JSON}")

else:
    print(f"  WARNING: No dataset file found.")
    print(f"  Expected one of:")
    print(f"    {INPUT_CSV}")
    print(f"    {INPUT_JSON}")
    print()
    print(f"  The DEMO above completed successfully.")
    print(f"  Run Day 4 preprocessing first to get devign_cleaned.csv")
    sys.exit(0)

print(f"  Total samples : {len(df)}")
print(f"  Columns       : {list(df.columns)}")

# ── Apply MAX_SAMPLES limit ────────────────────────────────────────────────────
if MAX_SAMPLES is not None and MAX_SAMPLES < len(df):
    df = df.head(MAX_SAMPLES).reset_index(drop=True)
    print()
    print(f"  NOTE: Processing only the first {MAX_SAMPLES} samples.")
    print(f"  To process ALL samples, set MAX_SAMPLES = None in the constants.")
    print(f"  Full processing is recommended on Google Colab with a free GPU.")

print(f"  Samples to process: {len(df)}")


# ── SECTION 9: EXTRACT EMBEDDINGS IN BATCHES ─────────────────────────────────
#
# Processing in batches is more efficient than one sample at a time.
# We divide the dataset into chunks of BATCH_SIZE, process each chunk,
# and accumulate results.

section("STEP 6: EXTRACTING EMBEDDINGS IN BATCHES")

print(f"  Batch size : {BATCH_SIZE}")
print(f"  Total      : {len(df)} samples")
n_batches = (len(df) + BATCH_SIZE - 1) // BATCH_SIZE
print(f"  Batches    : {n_batches}")
print()

all_embeddings = []   # will collect numpy arrays, one per batch
failed_indices = []   # track any samples that fail
resume_from = 0        # index (in df) to start processing from

# ── Resume from a previous checkpoint, if one exists ─────────────────────────
#
# We only trust a checkpoint if it was produced from the SAME dataset size
# as the current run (total_samples matches len(df)). Otherwise (e.g. the
# input CSV changed) we ignore it and start fresh, to avoid mixing
# embeddings computed from two different datasets.
if os.path.exists(CHECKPOINT_NPY) and os.path.exists(CHECKPOINT_META):
    with open(CHECKPOINT_META, "r", encoding="utf-8") as f:
        ckpt_meta = json.load(f)

    if ckpt_meta.get("total_samples") == len(df) and ckpt_meta.get("samples_done", 0) > 0:
        checkpoint_matrix = np.load(CHECKPOINT_NPY)
        resume_from = ckpt_meta["samples_done"]
        failed_indices = ckpt_meta.get("failed_indices", [])
        all_embeddings = [checkpoint_matrix]

        print(f"  Found checkpoint from a previous run:")
        print(f"    Samples already processed : {resume_from} / {len(df)}")
        print(f"    Resuming from sample index: {resume_from}")
    else:
        print(f"  Checkpoint found but does not match the current dataset size.")
        print(f"  Ignoring checkpoint and starting from sample 0.")

start_time = time.time()

for batch_start in range(resume_from, len(df), BATCH_SIZE):

    # ── Slice the DataFrame into one batch ───────────────────────────────────
    batch_end  = min(batch_start + BATCH_SIZE, len(df))
    batch_df   = df.iloc[batch_start:batch_end]
    batch_num  = batch_start // BATCH_SIZE + 1
    pct        = (batch_end / len(df)) * 100

    # Lightweight per-batch heartbeat: overwrite the same line with end="\r"
    print(f"  Batch {batch_num:4d}/{n_batches}  [{pct:5.1f}%]  "
          f"samples {batch_start}–{batch_end - 1}...", end="\r")

    # ── Get the code strings for this batch ──────────────────────────────────
    code_list = batch_df["func"].astype(str).tolist()

    # ── Extract embeddings ────────────────────────────────────────────────────
    # We wrap in try/except so one bad sample does not crash the whole run.
    try:
        batch_embeddings = extract_batch_embeddings(code_list)
        all_embeddings.append(batch_embeddings)

    except Exception as e:
        # If a batch fails, fill its rows with zeros and record the failure
        print(f"\n  Warning: Batch {batch_num} failed: {e}")
        print(f"  Filling with zeros for samples {batch_start}–{batch_end - 1}")
        zero_batch = np.zeros((len(code_list), EMBEDDING_DIM))
        all_embeddings.append(zero_batch)
        failed_indices.extend(range(batch_start, batch_end))

    # ── Detailed progress report every PROGRESS_EVERY batches ────────────────
    #
    # Shows: current batch, samples processed, percentage complete,
    # elapsed time, processing rate, and an estimated time remaining (ETA)
    # based on the average time-per-sample observed so far.
    if batch_num % PROGRESS_EVERY == 0 or batch_end == len(df):
        elapsed = time.time() - start_time
        samples_done = batch_end

        # IMPORTANT: rate must be computed from samples processed in THIS
        # run (batch_end - resume_from), not the absolute sample count.
        # If we resumed from a checkpoint, samples before resume_from took
        # zero time in this run -- dividing samples_done by elapsed would
        # silently inflate the rate and produce a wildly wrong ETA.
        samples_done_this_run = batch_end - resume_from
        rate = samples_done_this_run / elapsed if elapsed > 0 else 0.0
        remaining_samples = len(df) - samples_done
        eta_seconds = remaining_samples / rate if rate > 0 else 0.0

        print()  # move past the \r heartbeat line
        print(
            f"  [PROGRESS] Batch {batch_num}/{n_batches}  "
            f"Samples {samples_done}/{len(df)}  "
            f"({pct:5.1f}%)  "
            f"Elapsed: {elapsed/60:6.1f} min  "
            f"Rate: {rate:6.1f} samples/s  "
            f"ETA: {eta_seconds/60:6.1f} min"
        )

        # Periodically run garbage collection to release any lingering
        # Python objects (e.g. intermediate tokenizer lists) so memory
        # usage stays flat over a run of tens of thousands of samples.
        gc.collect()
        if DEVICE.type == "cuda":
            torch.cuda.empty_cache()

    # ── Write a resumable checkpoint every CHECKPOINT_EVERY batches ──────────
    #
    # If the process crashes or is interrupted after this point, the NEXT
    # run of this script will detect the checkpoint and resume from
    # `samples_done` instead of starting over from sample 0.
    if batch_num % CHECKPOINT_EVERY == 0 or batch_end == len(df):
        checkpoint_matrix = np.vstack(all_embeddings)
        np.save(CHECKPOINT_NPY, checkpoint_matrix)
        with open(CHECKPOINT_META, "w", encoding="utf-8") as f:
            json.dump({
                "total_samples": len(df),
                "samples_done": batch_end,
                "failed_indices": failed_indices,
            }, f)

# Clear the progress line
print()

total_elapsed = time.time() - start_time
print(f"  Total extraction time: {total_elapsed/60:.1f} minutes "
      f"({total_elapsed:.1f} seconds) for {len(df)} samples")

# ── Combine all batch results into one array ─────────────────────────────────
# np.vstack() stacks arrays vertically (on top of each other).
# Input:  list of arrays each of shape (BATCH_SIZE, 768)
# Output: one array of shape (total_samples, 768)
embedding_matrix = np.vstack(all_embeddings)

print(f"  Extraction complete.")
print(f"  Embedding matrix shape : {embedding_matrix.shape}")
print(f"     Rows    = {embedding_matrix.shape[0]}  (one per code function)")
print(f"     Columns = {embedding_matrix.shape[1]}  (768 dimensions per function)")
if failed_indices:
    print(f"  Failed samples (filled with zeros): {len(failed_indices)}")


# ── SECTION 10: SAVE EMBEDDINGS ────────────────────────────────────────────────

section("STEP 7: SAVING EMBEDDINGS")

os.makedirs(PROCESSED_DIR, exist_ok=True)

# ── Save as NumPy binary (.npy) ───────────────────────────────────────────────
#
# NumPy format is:
#   - Much smaller than CSV (stores raw binary, not text)
#   - Faster to load (no parsing needed)
#   - Preferred for large numerical arrays in ML pipelines
#
# np.save() creates a .npy file.
# Loading later: embedding_matrix = np.load(OUTPUT_NPY)

np.save(OUTPUT_NPY, embedding_matrix)
npy_size_mb = os.path.getsize(OUTPUT_NPY) / (1024 * 1024)
print(f"  NumPy saved  : {OUTPUT_NPY}")
print(f"  File size    : {npy_size_mb:.1f} MB")
print(f"  Shape stored : {embedding_matrix.shape}")

# ── Clean up the checkpoint now that the final output has been saved ─────────
#
# The checkpoint's only job was to protect an in-progress run. Once the real
# OUTPUT_NPY has been written successfully, the checkpoint is redundant --
# remove it so a future run doesn't mistake it for unfinished work.
for ckpt_path in (CHECKPOINT_NPY, CHECKPOINT_META):
    if os.path.exists(ckpt_path):
        os.remove(ckpt_path)
print(f"  Checkpoint files cleaned up.")

# ── Save metadata CSV (target labels and identifiers) ────────────────────────
#
# The metadata CSV links each row of the embedding matrix to its
# original sample (target label, project, commit ID).
# This is needed because the .npy file has no column headers.

meta_df = df[["target"]].copy()

if "project" in df.columns:
    meta_df["project"] = df["project"]
if "commit_id" in df.columns:
    meta_df["commit_id"] = df["commit_id"]

meta_df["embedding_row"] = range(len(df))   # row index in the .npy array

meta_df.to_csv(OUTPUT_META_CSV, index=False, encoding="utf-8")
print(f"  Metadata CSV : {OUTPUT_META_CSV}")

# ── Save full embeddings as CSV (as requested) ────────────────────────────────
#
# This creates a CSV with columns:
#   target, project, commit_id, embed_000, embed_001, ..., embed_767
#
# File size will be large (20-200 MB depending on number of samples).
# Column names "embed_000" through "embed_767" are zero-padded for sorting.

print()
print(f"  Building embeddings CSV (this may take a moment)...")

# Build column names: embed_000, embed_001, ..., embed_767
emb_col_names = [f"embed_{i:03d}" for i in range(EMBEDDING_DIM)]
# f"embed_{i:03d}" formats i as a 3-digit zero-padded integer:
#   i=0   → "embed_000"
#   i=1   → "embed_001"
#   i=767 → "embed_767"

# Convert the numpy array to a DataFrame with our named columns
emb_df = pd.DataFrame(
    embedding_matrix,
    columns=emb_col_names
)

# Round to 6 decimal places to keep the CSV file size manageable
emb_df = emb_df.round(6)

# Attach the metadata columns to the left of the embedding columns
full_df = pd.concat([meta_df.reset_index(drop=True), emb_df], axis=1)
# pd.concat(axis=1) joins DataFrames side by side (column-wise)

full_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
csv_size_mb = os.path.getsize(OUTPUT_CSV) / (1024 * 1024)

print(f"  Embeddings CSV : {OUTPUT_CSV}")
print(f"  File size      : {csv_size_mb:.1f} MB")
print(f"  Rows           : {len(full_df)}")
print(f"  Columns        : {len(full_df.columns)}")
print(f"     Metadata    : {len(meta_df.columns)} columns")
print(f"     Embeddings  : {EMBEDDING_DIM} columns  (embed_000 to embed_767)")


# ── SECTION 11: STATISTICS ─────────────────────────────────────────────────────

section("STEP 8: EMBEDDING STATISTICS BY LABEL")

vuln_mask     = full_df["target"] == 1
non_vuln_mask = full_df["target"] == 0

vuln_embs     = embedding_matrix[vuln_mask.values]
non_vuln_embs = embedding_matrix[non_vuln_mask.values]

print(f"  Vulnerable samples     : {vuln_embs.shape[0]}")
print(f"  Non-Vulnerable samples : {non_vuln_embs.shape[0]}")
print()
print(f"  Statistic             {'Vulnerable':>12} {'Non-Vuln':>12}")
print(f"  {'-'*38}")
print(f"  Mean of all dims      {vuln_embs.mean():>12.4f} {non_vuln_embs.mean():>12.4f}")
print(f"  Std of all dims       {vuln_embs.std():>12.4f} {non_vuln_embs.std():>12.4f}")
print(f"  Min value             {vuln_embs.min():>12.4f} {non_vuln_embs.min():>12.4f}")
print(f"  Max value             {vuln_embs.max():>12.4f} {non_vuln_embs.max():>12.4f}")

# Euclidean distance between mean embeddings of vulnerable and non-vulnerable
mean_v    = vuln_embs.mean(axis=0)     # average embedding of all vulnerable
mean_s    = non_vuln_embs.mean(axis=0) # average embedding of all non-vulnerable
eucl_dist = np.linalg.norm(mean_v - mean_s)
print()
print(f"  Euclidean distance between class mean embeddings: {eucl_dist:.4f}")
print()
if eucl_dist > 1.0:
    print("  The two classes are WELL-SEPARATED in embedding space.")
    print("  CodeBERT has learned meaningful differences between")
    print("  vulnerable and non-vulnerable code patterns.")
else:
    print("  The two classes are CLOSE in embedding space.")
    print("  This is expected — the embeddings capture general code")
    print("  semantics, not just vulnerability patterns. The classifier")
    print("  will learn to use subtle directions in the 768-D space.")


# ── DONE ──────────────────────────────────────────────────────────────────────

section("CODEBERT EMBEDDING EXTRACTION COMPLETE")
print(f"  Samples processed : {len(df)}")
print(f"  Embedding matrix  : {embedding_matrix.shape}")
print()
print("  Output files:")
print(f"    {OUTPUT_NPY}       (NumPy — fast to load)")
print(f"    {OUTPUT_CSV}  (CSV — human readable)")
print(f"    {OUTPUT_META_CSV}    (metadata — labels and IDs)")
print()
print("  Next steps:")
print("    Day 8 -- Combine AST + Metrics + CodeBERT into one feature matrix")
print("    Day 9 -- Train the multi-modal vulnerability classifier")
print()
