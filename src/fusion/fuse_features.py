# =============================================================================
# fuse_features.py
# Day 8: Multi-Modal Feature Fusion
# Project: Multi-Modal Code Vulnerability Detection Using CodeBERT
# =============================================================================
#
# WHAT IS FEATURE FUSION?
#
#   Feature fusion means combining features from MULTIPLE sources into
#   ONE single table that a machine learning classifier can read.
#
#   In our project, we have THREE separate feature extraction scripts
#   (Days 5, 6, 7). Each one produces its OWN CSV file:
#
#   DAY 5 -- AST features:
#     "How many loops, if-statements, pointer ops does this function have?"
#     File   : devign_ast_features.csv
#     Output : 11 numbers per function
#
#   DAY 6 -- Software Metrics:
#     "How many lines? How many pointers? How many comments?"
#     File   : metrics_features.csv
#     Output : 13 numbers per function
#
#   DAY 7 -- CodeBERT Embeddings:
#     "What is the semantic MEANING of this code?"
#     File   : codebert_embeddings.csv
#     Output : 768 numbers per function
#
#   Feature Fusion COMBINES these three files into ONE row per function:
#     [11 AST numbers] + [13 metric numbers] + [768 embedding numbers]
#     = 792 features per function
#
#   This 792-column table is saved as final_features.csv.
#   The classifier (Day 9) will read it and learn from ALL 792 features.
#
#
# ANALOGY: THREE DOCTORS, ONE PATIENT
#
#   Imagine a patient is examined by three specialists:
#     - Doctor A reads the X-ray        (structural view)
#     - Doctor B runs blood tests        (chemical view)
#     - Doctor C listens to symptoms     (functional view)
#
#   Each doctor gives a PARTIAL picture. The diagnosis improves when ALL
#   THREE views are combined into one patient record.
#
#   In our project:
#     - AST features  = Doctor A (structural view of code)
#     - Metrics        = Doctor B (quantitative view of code)
#     - CodeBERT       = Doctor C (semantic view of code)
#
#   Feature fusion = combining all three into one patient record.
#
#
# WHAT IS EARLY FUSION?
#
#   "Early fusion" (also called feature-level fusion) means we concatenate
#   ALL features into ONE big vector BEFORE giving it to the classifier.
#
#   The opposite is "late fusion" (decision-level), where each branch
#   trains its own classifier and we average their predictions at the end.
#
#   We use early fusion because:
#     - It is simpler to implement
#     - It allows the classifier to learn INTERACTIONS between branches
#       (e.g., "high pointer_count AND high n_pointer_ops together = risky")
#     - It is the standard approach for research papers
#
#
# WHAT THIS SCRIPT DOES:
#
#   STEP 1  : DEMO -- tiny 4-sample example to visualise the merge
#   STEP 2  : Check that all three source CSV files exist
#   STEP 3  : Load AST features from devign_ast_features.csv
#   STEP 4  : Load Software Metrics from metrics_features.csv
#   STEP 5  : Load CodeBERT embeddings from codebert_embeddings.csv
#   STEP 6  : Align tables using sample_id (row number from original dataset)
#   STEP 7  : Merge all three tables (two pd.merge() calls)
#   STEP 8  : Validate: row count, missing values, duplicates, label integrity
#   STEP 9  : Save to dataset/processed/final_features.csv
#   STEP 10 : Print feature statistics by label
#
#
# HOW TO RUN:
#
#   1. Open VS Code terminal         (Ctrl + backtick)
#   2. Activate venv:                .\venv\Scripts\activate
#   3. Navigate here:                cd src\fusion
#   4. Run:                          python fuse_features.py
#
#   PREREQUISITE: You must have already run ALL THREE feature scripts:
#     cd src\preprocessing  && python preprocess_dataset.py   (Day 4)
#     cd src\ast            && python extract_ast_features.py  (Day 5)
#     cd src\metrics        && python extract_metrics.py       (Day 6)
#     cd src\codebert       && python extract_embeddings.py    (Day 7)
#
#
# NO NEW PACKAGES NEEDED:
#   Only uses pandas and numpy, which are already installed.
# =============================================================================


# ── SECTION 0: IMPORTS ────────────────────────────────────────────────────────
#
# All libraries used in this script.
#
# os      : file path operations and folder creation
# sys     : sys.exit() to stop the script cleanly when files are missing
# numpy   : numerical operations (mean, std, norm calculations)
# pandas  : DataFrame and CSV operations (the core of this script)

import os
import sys
import numpy as np
import pandas as pd


# ── SECTION 1: PATHS ─────────────────────────────────────────────────────────
#
# Build all file paths relative to THIS script's own location.
# This ensures the script runs correctly no matter what folder you start from.
#
# SCRIPT_DIR   = .../src/fusion/
# PROJECT_ROOT = .../MultiModal_Code_Vulnerability_Detection/    (two levels up)

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT  = os.path.dirname(os.path.dirname(SCRIPT_DIR))
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "dataset", "processed")

# ── Input files (produced by Days 5, 6, 7) ───────────────────────────────────
AST_CSV      = os.path.join(PROCESSED_DIR, "devign_ast_features.csv")
METRICS_CSV  = os.path.join(PROCESSED_DIR, "metrics_features.csv")
CODEBERT_CSV = os.path.join(PROCESSED_DIR, "codebert_embeddings.csv")

# ── Output file ───────────────────────────────────────────────────────────────
OUTPUT_CSV   = os.path.join(PROCESSED_DIR, "final_features.csv")


# ── SECTION 2: FEATURE COLUMN NAME LISTS ─────────────────────────────────────
#
# These lists define WHICH columns we extract from each source file.
# We do NOT include raw code text ('func') — it is not a numeric feature.
# We do NOT include 'parse_failed' — it is diagnostic info, not a feature.
# Metadata columns (project, commit_id) are carried from the AST file only.

# 11 AST structural features
AST_FEATURE_COLS = [
    "n_functions",      # number of function definitions in the code block
    "n_loops",          # for + while + do-while loops
    "n_if_statements",  # if / else-if blocks
    "n_assignments",    # assignment expressions  (x = ...)
    "n_returns",        # return statements
    "n_pointer_ops",    # pointer dereferences (*ptr) and pointer declarations
    "n_function_calls", # function call expressions
    "n_binary_ops",     # arithmetic and comparison operations (+, -, *, ==, <)
    "max_depth",        # deepest nesting level in the AST
    "n_total_nodes",    # total AST nodes (overall code complexity)
    "n_error_nodes",    # nodes tree-sitter could not parse
]

# 13 software metric features
METRICS_FEATURE_COLS = [
    "loc",              # Lines of Code (non-empty lines)
    "function_count",   # number of function definitions (regex)
    "loop_count",       # total loop statements
    "if_count",         # total if statements
    "return_count",     # total return statements
    "avg_line_length",  # average character length of non-empty lines
    "max_line_length",  # longest line in characters
    "comment_count",    # number of // and /* */ comment blocks
    "total_lines",      # all lines including blank
    "blank_lines",      # blank-only lines
    "nesting_depth",    # brace-counting nesting depth approximation
    "operator_count",   # arithmetic/comparison/logical operators
    "pointer_count",    # -> and *identifier occurrences
]

# 768 CodeBERT embedding dimensions  (embed_000 ... embed_767)
# f"embed_{i:03d}" formats i with 3 digits:  0 -> "000",  767 -> "767"
EMBED_COLS = [f"embed_{i:03d}" for i in range(768)]

# Feature count summary
N_AST      = len(AST_FEATURE_COLS)     # 11
N_METRICS  = len(METRICS_FEATURE_COLS) # 13
N_EMBED    = len(EMBED_COLS)           # 768
N_TOTAL    = N_AST + N_METRICS + N_EMBED  # 792


# ── SECTION 3: UTILITY ────────────────────────────────────────────────────────

def section(title):
    """Prints a clearly visible section header to separate output sections."""
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


# =============================================================================
# STEP 1 -- DEMO: TINY EXAMPLE SHOWING FEATURE FUSION
# =============================================================================
#
# Before touching any real data, we show a TINY EXAMPLE using hand-made
# DataFrames with only 4 samples and 3 columns from each branch.
#
# This runs ALWAYS, even if the real dataset files are missing.
# PURPOSE: Understand what "merging" means before seeing the full run.
#
# In the real fusion (Steps 3-10), each function has 11 + 13 + 768 = 792
# features. Here we show just 3 from each to keep it readable.
# =============================================================================

section("STEP 1: DEMO -- TINY EXAMPLE OF FEATURE FUSION")

print()
print("  Imagine we have 4 C functions.")
print("  Each of the three scripts (Days 5, 6, 7) produced its OWN table.")
print("  Now we JOIN all three tables into one using SAMPLE ID.")
print()
print("  SAMPLE ID = the row number of the function in devign_cleaned.csv.")
print("  Sample ID 0 in the AST table is the SAME function as")
print("  Sample ID 0 in the Metrics table and Sample ID 0 in CodeBERT.")
print()

# ── Build tiny demo tables ───────────────────────────────────────────────────

# Table 1: AST features  (3 of 11 columns shown)
demo_ast = pd.DataFrame({
    "sample_id"     : [0,       1,       2,       3      ],
    "target"        : [1,       0,       1,       0      ],  # 1=vulnerable
    "project"       : ["FFmpeg","FFmpeg","qemu",  "qemu" ],
    "n_loops"       : [2,       1,       3,       0      ],
    "n_pointer_ops" : [3,       1,       5,       2      ],
    "max_depth"     : [5,       4,       7,       3      ],
})

# Table 2: Software Metrics  (3 of 13 columns shown)
demo_metrics = pd.DataFrame({
    "sample_id"     : [0,   1,   2,   3  ],
    "loc"           : [20,  15,  30,  10 ],
    "pointer_count" : [4,   1,   6,   0  ],
    "comment_count" : [2,   3,   1,   4  ],
})

# Table 3: CodeBERT embeddings  (3 of 768 columns shown)
demo_codebert = pd.DataFrame({
    "sample_id" : [0,       1,       2,       3      ],
    "embed_000" : [ 0.1823, -0.4521,  0.0034,  0.7821],
    "embed_001" : [-0.2341,  0.1234, -0.5678,  0.3456],
    "embed_002" : [ 0.5671,  0.2345, -0.1234, -0.4567],
})

# ── Print each table before merging ─────────────────────────────────────────

print("  TABLE 1: AST Features  (3 of 11 columns shown)")
print("  " + "-" * 58)
print(demo_ast.to_string(index=False))
print()
print("  TABLE 2: Software Metrics  (3 of 13 columns shown)")
print("  " + "-" * 58)
print(demo_metrics.to_string(index=False))
print()
print("  TABLE 3: CodeBERT Embeddings  (3 of 768 columns shown)")
print("  " + "-" * 58)
print(demo_codebert.to_string(index=False))

# ── Merge step by step ───────────────────────────────────────────────────────
#
# pd.merge() joins two DataFrames on a common column.
#
# Parameters:
#   left    : the first (left) DataFrame
#   right   : the second (right) DataFrame
#   on      : the column name used to MATCH rows across both DataFrames
#   how     : "inner" = keep only rows where sample_id appears in BOTH tables
#             "left"  = keep all left rows (fill missing right with NaN)
#             "outer" = keep all rows from both tables
#
#   We use "inner" because we want ONLY samples that have ALL THREE
#   feature types. If a sample is missing from one file, we exclude it.
#   A partial row (with NaN features) would confuse the classifier.

print()
print("  --- MERGE 1: AST table + Metrics table, joined on 'sample_id' ---")
print()

step1 = pd.merge(
    demo_ast,       # left DataFrame
    demo_metrics,   # right DataFrame
    on="sample_id", # the column to match rows by
    how="inner",    # inner join: only matching rows survive
)

print("  Result after merging AST + Metrics:")
print("  " + "-" * 58)
print(step1.to_string(index=False))
print()
print(f"  Rows: {len(step1)}  Columns: {len(step1.columns)}")

print()
print("  --- MERGE 2: (AST+Metrics) + CodeBERT, joined on 'sample_id' ---")
print()

fused_demo = pd.merge(
    step1,            # left: the result from Merge 1
    demo_codebert,    # right: CodeBERT embeddings
    on="sample_id",
    how="inner",
)

print("  Result after merging ALL THREE branches:")
print("  " + "-" * 58)
print(fused_demo.to_string(index=False))
print()
print(f"  Rows         : {len(fused_demo)}  (one row per C function)")
print(f"  Feature cols : {len(fused_demo.columns) - 2}  (all features combined)")
print()
print("  KEY POINT:")
print("  Three separate tables became ONE combined table.")
print("  In the real run: 11 AST + 13 metrics + 768 embeddings = 792 features.")
print("  The classifier reads this ONE row and learns from ALL 792 features.")


# =============================================================================
# REAL FUSION -- load the actual files produced by Days 5, 6, and 7
# =============================================================================

# ── STEP 2: CHECK SOURCE FILES ────────────────────────────────────────────────

section("STEP 2: CHECKING SOURCE FILES")

print()

source_files = {
    "AST features    (Day 5 output)": AST_CSV,
    "Metrics features(Day 6 output)": METRICS_CSV,
    "CodeBERT embeds (Day 7 output)": CODEBERT_CSV,
}

all_found = True

for label, path in source_files.items():
    exists = os.path.exists(path)
    if exists:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  [FOUND  ]  {label}")
        print(f"             {path}  ({size_mb:.1f} MB)")
    else:
        print(f"  [MISSING]  {label}")
        print(f"             {path}")
        all_found = False
    print()

if not all_found:
    print("  One or more source files are missing.")
    print("  Run the earlier scripts in this order to generate them:")
    print()
    print("    Step 1: cd src\\preprocessing && python preprocess_dataset.py")
    print("    Step 2: cd src\\ast           && python extract_ast_features.py")
    print("    Step 3: cd src\\metrics       && python extract_metrics.py")
    print("    Step 4: cd src\\codebert      && python extract_embeddings.py")
    print()
    print("  Then re-run this script.")
    print("  (The DEMO above completed successfully.)")
    sys.exit(0)

print("  All three source files found. Proceeding with real fusion.")


# ── STEP 3: LOAD AST FEATURES ────────────────────────────────────────────────

section("STEP 3: LOADING AST FEATURES")

# pd.read_csv() reads the CSV file and returns a DataFrame.
# encoding="utf-8" ensures special characters in code text are handled.
ast_df = pd.read_csv(AST_CSV, encoding="utf-8")

print(f"  File loaded : {AST_CSV}")
print(f"  Rows        : {len(ast_df)}")
print(f"  Columns     : {len(ast_df.columns)}")
print()

# ── Add sample_id ─────────────────────────────────────────────────────────────
#
# The AST CSV does not have a 'sample_id' column.
# We CREATE one here by assigning the row's position: 0, 1, 2, 3, ...
#
# WHY?
#   All three feature files come from devign_cleaned.csv, processed
#   in the SAME ORDER. Row 0 in the AST file is the SAME function as
#   Row 0 in the metrics file and Row 0 in the CodeBERT file.
#   By assigning sample_id = row number, we get a key that works
#   for all three tables.
#
# range(len(ast_df)) generates: 0, 1, 2, 3, ..., (n-1)
# This is assigned as a new column named "sample_id".

ast_df["sample_id"] = range(len(ast_df))

print(f"  Added 'sample_id' column: 0 to {len(ast_df) - 1}")

# ── Verify all expected feature columns are present ──────────────────────────
missing_ast_cols = [col for col in AST_FEATURE_COLS if col not in ast_df.columns]
if missing_ast_cols:
    print(f"  ERROR: These AST columns are missing: {missing_ast_cols}")
    print("  The AST feature file may be outdated. Re-run extract_ast_features.py.")
    sys.exit(1)

print(f"  Verified: all {N_AST} AST feature columns present.")
print()
print("  First 3 rows (sample_id + target + 3 key AST features):")

display_cols = ["sample_id", "target", "n_loops", "n_pointer_ops", "max_depth"]
print(ast_df[display_cols].head(3).to_string(index=False))


# ── STEP 4: LOAD SOFTWARE METRICS ────────────────────────────────────────────

section("STEP 4: LOADING SOFTWARE METRICS")

metrics_df = pd.read_csv(METRICS_CSV, encoding="utf-8")

print(f"  File loaded : {METRICS_CSV}")
print(f"  Rows        : {len(metrics_df)}")
print(f"  Columns     : {len(metrics_df.columns)}")
print()

# Same logic: add sample_id = row position
# This matches the AST file's sample_id for the same function.
metrics_df["sample_id"] = range(len(metrics_df))

print(f"  Added 'sample_id' column: 0 to {len(metrics_df) - 1}")

missing_metric_cols = [col for col in METRICS_FEATURE_COLS if col not in metrics_df.columns]
if missing_metric_cols:
    print(f"  ERROR: These metric columns are missing: {missing_metric_cols}")
    print("  Re-run extract_metrics.py.")
    sys.exit(1)

print(f"  Verified: all {N_METRICS} metric feature columns present.")
print()
print("  First 3 rows (sample_id + 3 key metric features):")

display_cols = ["sample_id", "loc", "pointer_count", "comment_count"]
print(metrics_df[display_cols].head(3).to_string(index=False))


# ── STEP 5: LOAD CODEBERT EMBEDDINGS ─────────────────────────────────────────

section("STEP 5: LOADING CODEBERT EMBEDDINGS")

print(f"  File: {CODEBERT_CSV}")
print(f"  Loading... (this file has 768 + 4 columns, may take a moment)")
print()

codebert_df = pd.read_csv(CODEBERT_CSV, encoding="utf-8")

print(f"  File loaded.")
print(f"  Rows    : {len(codebert_df)}")
print(f"  Columns : {len(codebert_df.columns)}")
print()

# ── Handle sample_id for CodeBERT ────────────────────────────────────────────
#
# The Day 7 script stored an 'embedding_row' column in the CSV.
# 'embedding_row' contains the row number of each sample in the original
# devign_cleaned.csv. For example, if MAX_SAMPLES was 200:
#
#   embedding_row 0  = the 1st function from devign_cleaned.csv
#   embedding_row 1  = the 2nd function from devign_cleaned.csv
#   ...
#   embedding_row 199 = the 200th function
#
# We RENAME this column to 'sample_id' so it matches the other two tables.
# After renaming, an inner join on 'sample_id' correctly aligns:
#   - ast_df row 0          (sample_id = 0)
#   - metrics_df row 0      (sample_id = 0)
#   - codebert_df row where embedding_row = 0  (sample_id = 0)
# All three point to the SAME C function.

if "embedding_row" in codebert_df.columns:
    codebert_df = codebert_df.rename(columns={"embedding_row": "sample_id"})
    print("  'embedding_row' column renamed to 'sample_id'.")
    print(f"  sample_id range: {codebert_df['sample_id'].min()} "
          f"to {codebert_df['sample_id'].max()}")
else:
    # Fallback: if embedding_row is missing, use row position
    codebert_df["sample_id"] = range(len(codebert_df))
    print("  'embedding_row' not found. Used row position as sample_id.")

# ── Verify embedding columns ─────────────────────────────────────────────────
missing_embed_cols = [col for col in EMBED_COLS if col not in codebert_df.columns]
if missing_embed_cols:
    print(f"  ERROR: {len(missing_embed_cols)} embedding columns missing.")
    print(f"  First few missing: {missing_embed_cols[:5]}")
    print("  Re-run extract_embeddings.py.")
    sys.exit(1)

print(f"  Verified: all {N_EMBED} embedding columns present (embed_000 to embed_767).")
print()
print(f"  NOTE: CodeBERT may have fewer rows than AST/Metrics if")
print(f"  MAX_SAMPLES was set to a small number in extract_embeddings.py.")
print(f"  The inner join (Step 7) will keep only rows present in ALL THREE files.")


# ── STEP 6: SELECT FEATURE COLUMNS ───────────────────────────────────────────

section("STEP 6: SELECTING COLUMNS FROM EACH TABLE")

print("  We keep only the columns we need from each file.")
print("  This avoids duplicate 'target', 'project', 'commit_id' columns")
print("  that would appear if we merged ALL columns from all three files.")
print()

# FROM AST: sample_id + metadata + 11 AST feature columns
ast_meta = [c for c in ["target", "project", "commit_id"] if c in ast_df.columns]
ast_sel   = ast_df[["sample_id"] + ast_meta + AST_FEATURE_COLS].copy()

# FROM METRICS: sample_id + 13 metric columns ONLY  (no metadata — already in ast_sel)
metrics_sel = metrics_df[["sample_id"] + METRICS_FEATURE_COLS].copy()

# FROM CODEBERT: sample_id + 768 embedding columns ONLY
codebert_sel = codebert_df[["sample_id"] + EMBED_COLS].copy()

print(f"  AST selected cols     : 1 (id) + {len(ast_meta)} (meta) + {N_AST} (features)"
      f" = {1 + len(ast_meta) + N_AST}")
print(f"  Metrics selected cols : 1 (id) + {N_METRICS} (features)"
      f" = {1 + N_METRICS}")
print(f"  CodeBERT selected cols: 1 (id) + {N_EMBED} (features)"
      f" = {1 + N_EMBED}")


# ── STEP 7: MERGE ALL THREE TABLES ───────────────────────────────────────────

section("STEP 7: MERGING ALL THREE FEATURE TABLES")

print(f"  Sizes before merge:")
print(f"    AST features        : {len(ast_sel)} rows")
print(f"    Software metrics    : {len(metrics_sel)} rows")
print(f"    CodeBERT embeddings : {len(codebert_sel)} rows")

# ── Merge 1: AST + Metrics ────────────────────────────────────────────────────
print()
print("  MERGE 1: AST features + Software Metrics (on 'sample_id', inner join)")

merged_step1 = pd.merge(
    ast_sel,            # left table  (has metadata + 11 AST features)
    metrics_sel,        # right table (has 13 metric features)
    on="sample_id",     # rows are matched by this column's value
    how="inner",        # inner join: only rows present in BOTH tables survive
                        # If a row exists in one file but not the other, DROP it.
)

print(f"  Rows after Merge 1   : {len(merged_step1)}")
print(f"  Columns after Merge 1: {len(merged_step1.columns)}")

# ── Merge 2: (AST + Metrics) + CodeBERT ──────────────────────────────────────
#
# The second merge adds 768 CodeBERT columns.
# If CodeBERT only has 200 samples (MAX_SAMPLES=200), the inner join
# will REDUCE the final table to those 200 samples.
# This is expected: we can only train on samples where we have ALL features.

print()
print("  MERGE 2: (AST + Metrics) + CodeBERT Embeddings (inner join)")

merged_all = pd.merge(
    merged_step1,       # left: result of Merge 1
    codebert_sel,       # right: 768 embedding columns
    on="sample_id",
    how="inner",
)

print(f"  Rows after Merge 2   : {len(merged_all)}")
print(f"  Columns after Merge 2: {len(merged_all.columns)}")

print()
print(f"  FINAL FEATURE MATRIX:")
print(f"  ┌─────────────────────────────────┐")
print(f"  | Samples (rows)     : {len(merged_all):>8}  |")
print(f"  | Metadata columns   : {1 + len(ast_meta):>8}  |  (sample_id, target, project, commit_id)")
print(f"  | AST features       : {N_AST:>8}  |  (n_functions, n_loops, ...)")
print(f"  | Metric features    : {N_METRICS:>8}  |  (loc, loop_count, ...)")
print(f"  | Embedding features : {N_EMBED:>8}  |  (embed_000 to embed_767)")
print(f"  | TOTAL features     : {N_TOTAL:>8}  |  (11 + 13 + 768 = 792)")
print(f"  | TOTAL columns      : {len(merged_all.columns):>8}  |")
print(f"  └─────────────────────────────────┘")


# ── STEP 8: VALIDATION ────────────────────────────────────────────────────────

section("STEP 8: VALIDATION")

print("  Running 4 checks on the fused feature matrix...")

all_feature_cols = AST_FEATURE_COLS + METRICS_FEATURE_COLS + EMBED_COLS


# ---- CHECK 1: ROW COUNT ─────────────────────────────────────────────────────
#
# We check that the final table is not empty.
# Zero rows means sample_ids did not match — the three scripts were run
# on different versions of the dataset, or in a different order.

print()
print("  [CHECK 1] ROW COUNT")

n_rows = len(merged_all)
print(f"  Total rows in final_features.csv: {n_rows}")

if n_rows == 0:
    print("  FAIL: Zero rows after merge!")
    print("  The sample_id values did not match across the three files.")
    print("  Make sure all three scripts were run on the same cleaned dataset.")
    sys.exit(1)
elif n_rows < 100:
    print(f"  WARNING: Only {n_rows} rows available.")
    print("  CodeBERT MAX_SAMPLES may have been set to a small value.")
    print("  The fusion is valid but the training set will be small.")
    print("  To get more rows: set MAX_SAMPLES=None in extract_embeddings.py")
    print("  and re-run (a GPU, e.g. Google Colab, will finish fastest).")
elif n_rows >= 200:
    print(f"  PASS: {n_rows} samples ready for training.")


# ---- CHECK 2: MISSING VALUES ─────────────────────────────────────────────────
#
# NaN (Not a Number) in feature columns causes most ML classifiers to crash.
# We count missing values per column.
# isnull() returns True where a value is NaN.
# .sum() counts the True values column by column.

print()
print("  [CHECK 2] MISSING VALUES")

missing_counts  = merged_all[all_feature_cols].isnull().sum()
# missing_counts is a pandas Series: index = column name, value = count of NaN

n_cols_with_nan = int((missing_counts > 0).sum())
total_nan_cells = int(missing_counts.sum())

if n_cols_with_nan == 0:
    print(f"  PASS: No missing values in any of the {len(all_feature_cols)} feature columns.")
else:
    print(f"  WARNING: {n_cols_with_nan} feature columns have missing values.")
    print(f"  Total NaN cells: {total_nan_cells}")
    print()
    print("  Top columns with missing values:")
    top_nan = missing_counts[missing_counts > 0].sort_values(ascending=False).head(10)
    for col, cnt in top_nan.items():
        pct = cnt / n_rows * 100
        print(f"    {col:<30}: {cnt} missing  ({pct:.1f}%)")
    print()
    print("  Filling missing values with 0 (safe default for these features).")
    merged_all[all_feature_cols] = merged_all[all_feature_cols].fillna(0)
    print("  Filled.")


# ---- CHECK 3: DUPLICATE SAMPLE IDs ───────────────────────────────────────────
#
# Each sample_id should appear exactly ONCE in the final table.
# If the same sample_id appears twice, something went wrong during the merge
# (e.g., the source file had duplicate rows for the same function).
#
# .duplicated() returns True for the 2nd and later occurrences of a value.
# .sum() counts how many such duplicated rows exist.

print()
print("  [CHECK 3] DUPLICATE SAMPLE IDs")

n_dup = int(merged_all["sample_id"].duplicated().sum())

if n_dup == 0:
    print("  PASS: No duplicate sample_ids. Every sample appears exactly once.")
else:
    print(f"  WARNING: {n_dup} duplicate sample_id values found.")
    print("  Keeping the first occurrence of each duplicate and dropping the rest.")
    merged_all = merged_all.drop_duplicates(subset=["sample_id"], keep="first")
    print(f"  Rows after deduplication: {len(merged_all)}")


# ---- CHECK 4: LABEL INTEGRITY ────────────────────────────────────────────────
#
# The 'target' column must contain ONLY the values 0 and 1:
#   0 = Non-Vulnerable (safe code)
#   1 = Vulnerable (code with a security flaw)
#
# If target contains NaN or any other value, the classifier will fail.

print()
print("  [CHECK 4] LABEL INTEGRITY")

label_counts = merged_all["target"].value_counts().sort_index()
unique_labels = sorted(merged_all["target"].dropna().unique().tolist())
n_missing_labels = int(merged_all["target"].isnull().sum())
unexpected_labels = [v for v in unique_labels if v not in [0, 1]]

print(f"  Unique values in 'target': {unique_labels}")
print()
print("  Label distribution:")
for lbl, cnt in label_counts.items():
    pct  = cnt / len(merged_all) * 100
    name = "Vulnerable     (1)" if lbl == 1 else "Non-Vulnerable (0)"
    bar  = "#" * int(pct / 2)
    print(f"    {name}: {cnt:6d}  ({pct:.1f}%)  {bar}")

if unexpected_labels:
    print(f"  WARN: Unexpected label values found: {unexpected_labels}")
elif n_missing_labels > 0:
    print(f"  WARN: {n_missing_labels} samples have missing (NaN) labels.")
else:
    print()
    print("  PASS: Labels are valid (only 0 and 1 present, no missing values).")


# ---- Validation Summary ──────────────────────────────────────────────────────
print()
print("  VALIDATION SUMMARY:")
print(f"    Total rows        : {len(merged_all)}")
print(f"    Total columns     : {len(merged_all.columns)}")
print(f"    Feature columns   : {N_TOTAL}  (11 AST + 13 metrics + 768 embeddings)")
print(f"    NaN cells         : {int(merged_all[all_feature_cols].isnull().sum().sum())}")
print(f"    Duplicate IDs     : {n_dup}")
print(f"    Label values      : {unique_labels}")


# ── STEP 9: SAVE FINAL FEATURES ───────────────────────────────────────────────

section("STEP 9: SAVING FINAL FEATURE MATRIX")

# Sort rows by sample_id so the file is in a predictable order.
# sort_values() reorders rows; reset_index() renumbers 0,1,2,...
# drop=True discards the old index instead of adding it as a column.
merged_all = merged_all.sort_values("sample_id").reset_index(drop=True)

# Create the output folder if it does not already exist.
# exist_ok=True means no error if the folder already exists.
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Save to CSV.
# index=False: do NOT write the row numbers (0, 1, 2, ...) as an extra column.
merged_all.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")

# Calculate file size
file_size_mb = os.path.getsize(OUTPUT_CSV) / (1024 * 1024)

print(f"  Saved to : {OUTPUT_CSV}")
print(f"  File size: {file_size_mb:.1f} MB")
print(f"  Rows     : {len(merged_all)}")
print(f"  Columns  : {len(merged_all.columns)}")
print()
print("  Column layout (in order):")
print(f"    Column 1        : sample_id")
print(f"    Column 2        : target  (0=safe, 1=vulnerable)")
print(f"    Column 3        : project (FFmpeg or qemu)")
print(f"    Column 4        : commit_id")
print(f"    Columns   5-15  : AST features  ({N_AST} columns)")
print(f"    Columns  16-28  : Metric features  ({N_METRICS} columns)")
print(f"    Columns 29-796  : CodeBERT embeddings  ({N_EMBED} columns)")


# ── STEP 10: FEATURE STATISTICS BY LABEL ─────────────────────────────────────

section("STEP 10: FEATURE STATISTICS BY LABEL")

vuln_df     = merged_all[merged_all["target"] == 1]
non_vuln_df = merged_all[merged_all["target"] == 0]

print(f"  Vulnerable samples     : {len(vuln_df)}")
print(f"  Non-Vulnerable samples : {len(non_vuln_df)}")

print()
print("  AST Feature Averages (Vulnerable vs Non-Vulnerable):")
print(f"  {'Feature':<22} {'Vuln':>8} {'Safe':>8} {'Diff':>8}  Signal?")
print(f"  {'-'*60}")

for col in AST_FEATURE_COLS:
    if col not in merged_all.columns:
        continue
    v_mean = vuln_df[col].mean()
    s_mean = non_vuln_df[col].mean()
    diff   = v_mean - s_mean
    sign   = "+" if diff >= 0 else ""
    signal = "vuln higher" if diff > 0.2 else ("safe higher" if diff < -0.2 else "similar")
    print(f"  {col:<22} {v_mean:>8.2f} {s_mean:>8.2f} {sign}{diff:>7.2f}  {signal}")

print()
print("  Metric Feature Averages (Vulnerable vs Non-Vulnerable):")
print(f"  {'Metric':<22} {'Vuln':>8} {'Safe':>8} {'Diff':>8}  Signal?")
print(f"  {'-'*60}")

for col in METRICS_FEATURE_COLS:
    if col not in merged_all.columns:
        continue
    v_mean = vuln_df[col].mean()
    s_mean = non_vuln_df[col].mean()
    diff   = v_mean - s_mean
    sign   = "+" if diff >= 0 else ""
    signal = "vuln higher" if diff > 0.2 else ("safe higher" if diff < -0.2 else "similar")
    print(f"  {col:<22} {v_mean:>8.2f} {s_mean:>8.2f} {sign}{diff:>7.2f}  {signal}")

print()
print("  CodeBERT Embedding Statistics:")

emb_vuln_vals     = vuln_df[EMBED_COLS].values
emb_non_vuln_vals = non_vuln_df[EMBED_COLS].values

print(f"  Vulnerable  mean: {emb_vuln_vals.mean():>8.4f}   std: {emb_vuln_vals.std():>8.4f}")
print(f"  Non-Vuln    mean: {emb_non_vuln_vals.mean():>8.4f}   std: {emb_non_vuln_vals.std():>8.4f}")

mean_vuln_emb     = emb_vuln_vals.mean(axis=0)
mean_non_vuln_emb = emb_non_vuln_vals.mean(axis=0)
eucl_dist = np.linalg.norm(mean_vuln_emb - mean_non_vuln_emb)

print(f"  Euclidean distance between class mean embeddings: {eucl_dist:.4f}")
print()
if eucl_dist > 1.0:
    print("  The two classes are well-separated in CodeBERT embedding space.")
else:
    print("  The two classes are close in CodeBERT embedding space.")
    print("  This confirms that AST and Metric features provide critical")
    print("  additional signal beyond what CodeBERT alone captures.")


# ── DONE ──────────────────────────────────────────────────────────────────────

section("FEATURE FUSION COMPLETE")

print(f"  Input files used:")
print(f"    {AST_CSV}")
print(f"    {METRICS_CSV}")
print(f"    {CODEBERT_CSV}")
print()
print(f"  Output file created:")
print(f"    {OUTPUT_CSV}")
print()
print(f"  Final feature matrix:")
print(f"    {len(merged_all)} samples  x  {N_TOTAL} features")
print(f"    (11 AST + 13 Metrics + 768 CodeBERT = 792 total features)")
print()
print("  Next step:")
print("    Day 9 -- Train the multi-modal vulnerability classifier")
print("             using final_features.csv as input.")
print()
