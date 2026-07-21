# =============================================================================
# preprocess_dataset.py
# Day 4: Dataset Preprocessing
# Project: Multi-Modal Code Vulnerability Detection Using CodeBERT
# =============================================================================
#
# What this script does (in order):
#   STEP 1  : Locate the raw dataset file(s)
#   STEP 2  : Load the data into a DataFrame
#   STEP 3  : Data Quality Check — report problems BEFORE cleaning
#   STEP 4  : Remove rows with missing (null) values
#   STEP 5  : Remove duplicate rows
#   STEP 6  : Remove empty code strings
#   STEP 7  : Remove abnormally short code samples
#   STEP 8  : Clean whitespace inside code strings
#   STEP 9  : Generate final statistics
#   STEP 10 : Save the cleaned dataset to dataset/processed/
#   STEP 11 : Save a quality report to dataset/notes/
#
# HOW TO RUN:
#   1. Open VS Code terminal
#   2. Activate venv:   .\venv\Scripts\activate
#   3. Go to this folder: cd src\preprocessing
#   4. Run: python preprocess_dataset.py
# =============================================================================


# ── IMPORTS ───────────────────────────────────────────────────────────────────

import json      # reads .json and .jsonl files
import pandas as pd  # for working with tabular data
import os        # for file paths and folder creation
import re        # for regular expressions (pattern-based text cleaning)


# ── PATH SETUP ────────────────────────────────────────────────────────────────
#
# __file__  is a special Python variable that holds the path of THIS script.
# os.path.abspath() converts it to a full absolute path.
# os.path.dirname() gets the folder containing the file.
#
# So:
#   SCRIPT_DIR   = .../MultiModal.../src/preprocessing/
#   PROJECT_ROOT = .../MultiModal.../                   (two levels up)

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

RAW_DIR       = os.path.join(PROJECT_ROOT, "dataset", "raw")
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "dataset", "processed")
NOTES_DIR     = os.path.join(PROJECT_ROOT, "dataset", "notes")

# Functions shorter than this (in characters) will be removed as too small
MIN_FUNC_LENGTH = 50


# ── UTILITY: PRINT A SECTION HEADER ───────────────────────────────────────────

def section(title):
    """Prints a visible header line to separate output sections."""
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


# ── STEP 1: LOCATE THE DATASET FILE ──────────────────────────────────────────
#
# The Devign dataset can come in two formats:
#   a) function.json  — one big JSON array (all samples in one file)
#   b) train.jsonl / valid.jsonl / test.jsonl — one JSON object per line
#
# We check for both and load whatever is present.

section("STEP 1: LOCATING DATASET FILES")

# List all files in the raw/ folder
all_raw_files = os.listdir(RAW_DIR) if os.path.exists(RAW_DIR) else []
print(f"  Files found in dataset/raw/  : {all_raw_files}")

# Decide which loading strategy to use
json_file  = os.path.join(RAW_DIR, "function.json")
jsonl_files = [
    os.path.join(RAW_DIR, "train.jsonl"),
    os.path.join(RAW_DIR, "valid.jsonl"),
    os.path.join(RAW_DIR, "test.jsonl"),
]

has_json  = os.path.exists(json_file)
has_jsonl = any(os.path.exists(f) for f in jsonl_files)

if not has_json and not has_jsonl:
    print()
    print("  ERROR: No dataset file found in dataset/raw/")
    print("  Expected one of:")
    print("    - function.json")
    print("    - train.jsonl  +  valid.jsonl  +  test.jsonl")
    print()
    print("  Please download the Devign dataset first (see Day 3 guide).")
    exit()

print(f"  function.json present : {has_json}")
print(f"  .jsonl files present  : {has_jsonl}")


# ── STEP 2: LOAD THE DATA ─────────────────────────────────────────────────────

section("STEP 2: LOADING DATA")

all_records = []   # will collect all samples from all files

if has_json:
    # ── Load the single function.json file ──
    print(f"  Loading: function.json")
    with open(json_file, "r", encoding="utf-8") as f:
        records = json.load(f)    # returns a Python list of dicts
    print(f"  Records loaded from function.json : {len(records)}")
    all_records.extend(records)   # add them all to our main list

else:
    # ── Load each .jsonl file line by line ──
    # .jsonl means each LINE is a separate JSON object
    for filepath in jsonl_files:
        if os.path.exists(filepath):
            filename = os.path.basename(filepath)
            print(f"  Loading: {filename}")
            with open(filepath, "r", encoding="utf-8") as f:
                for line_number, line in enumerate(f, start=1):
                    line = line.strip()       # remove leading/trailing whitespace
                    if line:                  # skip completely empty lines
                        record = json.loads(line)  # parse one line as JSON
                        all_records.append(record)
            print(f"    Records loaded so far : {len(all_records)}")

# Convert the Python list of dicts into a Pandas DataFrame (a table)
df = pd.DataFrame(all_records)

print()
print(f"  Total records loaded      : {len(df)}")
print(f"  Columns available         : {list(df.columns)}")


# ── STEP 3: DATA QUALITY CHECK (BEFORE CLEANING) ─────────────────────────────
#
# Before changing anything, we LOOK at the data to understand its problems.
# This is called a "quality audit".

section("STEP 3: DATA QUALITY CHECK (BEFORE CLEANING)")

# Record the original size so we can compare later
original_size = len(df)
print(f"  Original dataset size          : {original_size} samples")

# ── Check 1: Missing (null) values ──
# isnull() returns True for every cell that is missing or NaN
# .sum() counts how many True values are in each column
print()
print("  [CHECK 1] Missing values per column:")
missing_counts = df.isnull().sum()
for col in df.columns:
    count = missing_counts[col]
    status = "OK" if count == 0 else f"WARNING — {count} missing"
    print(f"    {col:<15} : {status}")

total_missing_rows = df.isnull().any(axis=1).sum()
# axis=1 means "check across columns" — True if ANY column is null in that row
print(f"  Total rows with at least one missing value : {total_missing_rows}")

# ── Check 2: Duplicate rows ──
# duplicated() returns True for rows that are identical to a previous row
# subset=["func"] means: two rows are duplicates if their code is the same
duplicate_count = df.duplicated(subset=["func"]).sum()
print()
print(f"  [CHECK 2] Duplicate rows (same code)      : {duplicate_count}")

# ── Check 3: Empty code strings ──
# An empty string "" has length 0 — it is useless for analysis
empty_func_count = (df["func"].str.strip() == "").sum()
# .str.strip() removes whitespace before checking for empty
print(f"  [CHECK 3] Empty code strings               : {empty_func_count}")

# ── Check 4: Abnormally short functions ──
# Functions shorter than 50 characters are likely incomplete or malformed
df["func_length"] = df["func"].str.len()
short_count = (df["func_length"] < MIN_FUNC_LENGTH).sum()
print(f"  [CHECK 4] Functions shorter than {MIN_FUNC_LENGTH} chars  : {short_count}")

# ── Check 5: Label validity ──
# Labels should only be 0 or 1 — anything else is an error
valid_labels = {0, 1}
invalid_label_count = (~df["target"].isin(valid_labels)).sum()
# ~ means "NOT" — so this counts rows where target is NOT 0 or 1
print()
print(f"  [CHECK 5] Rows with invalid labels (not 0 or 1) : {invalid_label_count}")

# ── Label distribution before cleaning ──
print()
print("  Label distribution BEFORE cleaning:")
before_label_counts = df["target"].value_counts().sort_index()
for label, count in before_label_counts.items():
    name = "Vulnerable (1)" if label == 1 else "Non-Vulnerable (0)"
    pct  = (count / len(df)) * 100
    print(f"    {name} : {count}  ({pct:.1f}%)")


# ── STEP 4: REMOVE ROWS WITH MISSING VALUES ───────────────────────────────────
#
# dropna() removes any row that has at least one missing (NaN) value.
# subset=["func", "target"] — we only care about these two essential columns.

section("STEP 4: REMOVING ROWS WITH MISSING VALUES")

before = len(df)
df = df.dropna(subset=["func", "target"])
after  = len(df)
removed = before - after

print(f"  Rows before : {before}")
print(f"  Rows removed: {removed}")
print(f"  Rows after  : {after}")


# ── STEP 5: REMOVE DUPLICATE ROWS ────────────────────────────────────────────
#
# keep="first" means if two rows have the same code, keep the FIRST one
# and remove the later ones.

section("STEP 5: REMOVING DUPLICATE ROWS")

before = len(df)
df = df.drop_duplicates(subset=["func"], keep="first")
after  = len(df)
removed = before - after

print(f"  Rows before : {before}")
print(f"  Rows removed: {removed}  (duplicate code strings)")
print(f"  Rows after  : {after}")


# ── STEP 6: REMOVE EMPTY CODE STRINGS ────────────────────────────────────────
#
# We keep only rows where the 'func' column is NOT empty after stripping spaces.

section("STEP 6: REMOVING EMPTY CODE STRINGS")

before = len(df)
df = df[df["func"].str.strip() != ""]
after  = len(df)
removed = before - after

print(f"  Rows before : {before}")
print(f"  Rows removed: {removed}  (empty code strings)")
print(f"  Rows after  : {after}")


# ── STEP 7: REMOVE ABNORMALLY SHORT FUNCTIONS ─────────────────────────────────
#
# A function with fewer than 50 characters cannot contain meaningful logic.
# These are likely extraction errors or header stubs.

section("STEP 7: REMOVING ABNORMALLY SHORT FUNCTIONS")

# Recalculate func_length after previous cleaning steps
df["func_length"] = df["func"].str.len()

before  = len(df)
df      = df[df["func_length"] >= MIN_FUNC_LENGTH]
after   = len(df)
removed = before - after

print(f"  Minimum length threshold : {MIN_FUNC_LENGTH} characters")
print(f"  Rows before : {before}")
print(f"  Rows removed: {removed}  (too short)")
print(f"  Rows after  : {after}")


# ── STEP 8: CLEAN WHITESPACE IN CODE STRINGS ──────────────────────────────────
#
# Real code sometimes has:
#   - Windows-style line endings (\r\n) instead of Unix (\n)
#   - Trailing spaces at the end of lines
#   - Multiple blank lines in a row
#
# We normalize all of this without changing the actual code logic.

section("STEP 8: CLEANING WHITESPACE IN CODE STRINGS")

def clean_code(code_string):
    """
    Cleans up whitespace in a code string.
    Does NOT change the logic or structure of the code.
    """
    # Replace Windows line endings (\r\n) with Unix line endings (\n)
    code_string = code_string.replace("\r\n", "\n")
    code_string = code_string.replace("\r", "\n")

    # Split the code into individual lines
    lines = code_string.split("\n")

    # Remove trailing spaces from the right end of each line
    lines = [line.rstrip() for line in lines]

    # Join the lines back together
    code_string = "\n".join(lines)

    # Replace 3 or more consecutive blank lines with just 2 blank lines
    # re.sub() is a "find and replace" using patterns
    # \n{3,} means "3 or more newline characters in a row"
    code_string = re.sub(r"\n{3,}", "\n\n", code_string)

    # Remove leading and trailing whitespace from the whole function
    code_string = code_string.strip()

    return code_string

# Apply the clean_code function to every row in the 'func' column
# .apply() runs a function on each value in the column
df["func"] = df["func"].apply(clean_code)

# Recalculate lengths after cleaning (whitespace removal changes lengths slightly)
df["func_length"] = df["func"].str.len()

print("  Whitespace cleaning applied to all code strings.")
print("  Changes made:")
print("    - Windows line endings converted to Unix (\\r\\n → \\n)")
print("    - Trailing spaces removed from each line")
print("    - Multiple consecutive blank lines collapsed")
print("    - Leading/trailing whitespace stripped")


# ── STEP 9: FINAL STATISTICS ──────────────────────────────────────────────────

section("STEP 9: FINAL DATASET STATISTICS")

final_size        = len(df)
vuln_count        = (df["target"] == 1).sum()
non_vuln_count    = (df["target"] == 0).sum()
vuln_pct          = (vuln_count   / final_size) * 100
non_vuln_pct      = (non_vuln_count / final_size) * 100
avg_length        = df["func_length"].mean()
min_length        = df["func_length"].min()
max_length        = df["func_length"].max()
median_length     = df["func_length"].median()
total_removed     = original_size - final_size

print(f"  Original dataset size          : {original_size}")
print(f"  Samples removed (total)        : {total_removed}")
print(f"  Final cleaned dataset size     : {final_size}")
print()
print(f"  Vulnerable samples (label=1)   : {vuln_count}  ({vuln_pct:.1f}%)")
print(f"  Non-Vulnerable samples (label=0): {non_vuln_count}  ({non_vuln_pct:.1f}%)")
print()
print(f"  Average function length        : {avg_length:.0f} characters")
print(f"  Median function length         : {median_length:.0f} characters")
print(f"  Shortest function              : {min_length} characters")
print(f"  Longest function               : {max_length} characters")

# Distribution by project (if the column exists)
if "project" in df.columns:
    print()
    print("  Samples per source project:")
    for project, count in df["project"].value_counts().items():
        pct = (count / final_size) * 100
        print(f"    {project:<12} : {count}  ({pct:.1f}%)")


# ── STEP 9.5: ASSIGN A STABLE ORIGINAL SAMPLE ID ─────────────────────────────
#
# Phase 4 forensic audit finding (docs/ML_FORENSIC_AUDIT_PHASE4.md): every
# downstream extraction script (AST, metrics) used to invent its OWN
# sample_id as `range(len(its_own_output))` -- which silently desynced from
# the other scripts' numbering the moment either one dropped a different set
# of rows (they used different, inconsistent length filters: 50 chars vs. 10
# chars). Empirically, this caused 27,048 of 27,225 fused rows (99.35%) to
# pair one function's label/AST features with a DIFFERENT function's
# metrics/CodeBERT features.
#
# The fix: assign the stable ID exactly ONCE, here, immediately after
# cleaning, tied to this DataFrame's row position at the moment it is first
# saved -- every downstream script reads and CARRIES this same column
# forward (never recomputes it from its own output length), and
# fuse_features.py joins on THIS column, not a locally-recomputed range().
df = df.reset_index(drop=True)
df["original_id"] = range(len(df))


# ── STEP 10: SAVE THE CLEANED DATASET ────────────────────────────────────────
#
# We save in two formats:
#   a) CSV — easy to open in Excel or pandas
#   b) JSON — keeps the structure close to the original, easy to reload

section("STEP 10: SAVING CLEANED DATASET")

# Make sure the output folder exists (create it if it doesn't)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# ── Save as CSV ──
csv_path = os.path.join(PROCESSED_DIR, "devign_cleaned.csv")

# We drop the helper column 'func_length' before saving — it was only for analysis
df.drop(columns=["func_length"]).to_csv(csv_path, index=False, encoding="utf-8")
print(f"  CSV saved  : {csv_path}")
print(f"  Assigned a stable 'original_id' column (0 to {len(df) - 1}) -- every")
print(f"  downstream extraction script must carry this column forward unchanged.")

# ── Save as JSON ──
json_out_path = os.path.join(PROCESSED_DIR, "devign_cleaned.json")
records_to_save = df.drop(columns=["func_length"]).to_dict(orient="records")
# orient="records" converts the DataFrame back into a list of dicts

with open(json_out_path, "w", encoding="utf-8") as f:
    json.dump(records_to_save, f, indent=2, ensure_ascii=False)
    # indent=2 makes the JSON human-readable with 2-space indentation
    # ensure_ascii=False preserves non-ASCII characters

print(f"  JSON saved : {json_out_path}")

# ── Verify the saved file ──
# Read back the CSV to confirm it saved correctly
verify_df = pd.read_csv(csv_path)
print()
print(f"  Verification — rows in saved CSV : {len(verify_df)}")
print(f"  Verification — columns in CSV    : {list(verify_df.columns)}")


# ── STEP 11: SAVE QUALITY REPORT ─────────────────────────────────────────────
#
# Write a Markdown summary of what we found and what we did.

section("STEP 11: SAVING QUALITY REPORT")

os.makedirs(NOTES_DIR, exist_ok=True)

report_path = os.path.join(NOTES_DIR, "data_quality_report.md")

report_content = f"""# Data Quality Report
**Project:** Multi-Modal Code Vulnerability Detection Using CodeBERT
**Day:** 4 — Dataset Preprocessing
**Script:** src/preprocessing/preprocess_dataset.py

---

## Original Dataset
- Total samples before cleaning : **{original_size}**

---

## Quality Issues Found

| Check | Issue | Count |
|---|---|---|
| Missing values | Rows with null in func or target | {total_missing_rows} |
| Duplicates | Rows with identical code strings | {duplicate_count} |
| Empty strings | Rows where func is blank | {empty_func_count} |
| Short functions | Functions under {MIN_FUNC_LENGTH} characters | {short_count} |
| Invalid labels | Labels that are not 0 or 1 | {invalid_label_count} |

---

## Cleaning Steps Applied

1. **Removed null rows** — dropped rows missing func or target
2. **Removed duplicates** — kept first occurrence of each unique function
3. **Removed empty strings** — dropped rows where func was empty or whitespace only
4. **Removed short functions** — dropped functions shorter than {MIN_FUNC_LENGTH} characters
5. **Cleaned whitespace** — normalized line endings, removed trailing spaces

---

## After Cleaning

| Metric | Value |
|---|---|
| Final dataset size | {final_size} |
| Samples removed | {total_removed} |
| Vulnerable (label=1) | {vuln_count} ({vuln_pct:.1f}%) |
| Non-Vulnerable (label=0) | {non_vuln_count} ({non_vuln_pct:.1f}%) |
| Average function length | {avg_length:.0f} characters |
| Median function length | {median_length:.0f} characters |
| Shortest function | {min_length} characters |
| Longest function | {max_length} characters |

---

## Output Files

| File | Location |
|---|---|
| Cleaned dataset (CSV) | dataset/processed/devign_cleaned.csv |
| Cleaned dataset (JSON) | dataset/processed/devign_cleaned.json |

---
*Report auto-generated by preprocess_dataset.py*
"""

with open(report_path, "w", encoding="utf-8") as f:
    f.write(report_content)

print(f"  Report saved : {report_path}")

# ── DONE ──────────────────────────────────────────────────────────────────────

section("PREPROCESSING COMPLETE")
print("  Summary:")
print(f"    Original size    : {original_size}")
print(f"    Cleaned size     : {final_size}")
print(f"    Samples removed  : {total_removed}")
print()
print("  Output files:")
print(f"    {csv_path}")
print(f"    {json_out_path}")
print(f"    {report_path}")
print()
print("  Next step: Day 5 — Feature Extraction")
print()
