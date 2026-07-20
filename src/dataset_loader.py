# =============================================================================
# dataset_loader.py
# Day 3: Dataset Exploration
# Project: Multi-Modal Code Vulnerability Detection Using CodeBERT
# =============================================================================
# What this script does:
#   1. Loads the Devign dataset (function.json)
#   2. Converts it into a table (DataFrame)
#   3. Prints basic information about the dataset
#   4. Counts vulnerable vs non-vulnerable samples
#   5. Displays one sample function from each category
# =============================================================================

# ── IMPORTS ──────────────────────────────────────────────────────────────────
# 'json'   : built-in Python library to read JSON files
# 'pandas' : popular data analysis library (tables, filtering, statistics)
# 'os'     : built-in library for file and folder path operations

import json
import pandas as pd
import os

# ── STEP 1: Define the path to the dataset file ──────────────────────────────
# os.path.join() builds a file path that works on Windows, Mac, and Linux.
# ".."  means "go one folder up" (from src/ back to the project root)
# Then it goes into dataset/raw/function.json

DATASET_PATH = os.path.join("..", "dataset", "raw", "function.json")

# ── STEP 2: Check that the file actually exists before trying to open it ─────
# This gives a clear error message if the file is missing.

if not os.path.exists(DATASET_PATH):
    print("ERROR: Dataset file not found at:", DATASET_PATH)
    print("Please make sure function.json is inside dataset/raw/")
    exit()

# ── STEP 3: Open and load the JSON file ──────────────────────────────────────
# 'open()' opens the file for reading ("r").
# 'encoding="utf-8"' handles special characters in the code strings.
# 'json.load(f)' reads the entire file and converts it into a Python list.
# Each item in the list is one code function (a dictionary with 4 keys).

print("Loading dataset... please wait.")

with open(DATASET_PATH, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

print(f"File loaded successfully. Type of data: {type(raw_data)}")

# ── STEP 4: Convert the list of dictionaries into a Pandas DataFrame ──────────
# A DataFrame is like an Excel spreadsheet — rows and columns.
# Each row = one code function.
# Each column = one piece of information (func, target, project, commit_id).

df = pd.DataFrame(raw_data)

# ── STEP 5: Print dataset size ────────────────────────────────────────────────
# len(df) gives the number of rows (samples).
# len(df.columns) gives the number of columns (fields).

print()
print("=" * 60)
print("  DATASET SIZE")
print("=" * 60)
print(f"  Total number of samples (rows)   : {len(df)}")
print(f"  Total number of columns (fields) : {len(df.columns)}")

# ── STEP 6: Print all column names ────────────────────────────────────────────
# df.columns gives a list of column names.
# We loop through them and print each one with a number.

print()
print("=" * 60)
print("  COLUMN NAMES")
print("=" * 60)
for index, column_name in enumerate(df.columns):
    print(f"  Column {index + 1}: {column_name}")

# ── STEP 7: Display the first 5 rows ──────────────────────────────────────────
# df.head() returns the first 5 rows by default.
# We shorten the 'func' column to 80 characters so it fits on screen.
# The actual code in 'func' can be hundreds of lines long.

print()
print("=" * 60)
print("  FIRST 5 ROWS  (code preview: first 80 characters only)")
print("=" * 60)

preview_df = df.copy()
preview_df["func"] = preview_df["func"].str[:80] + " ..."
print(preview_df.head().to_string(index=False))

# ── STEP 8: Count vulnerable vs non-vulnerable samples ────────────────────────
# df["target"] selects the 'target' column (the label column).
# value_counts() counts how many times each unique value appears.
# sort_index() makes sure label 0 appears before label 1.

print()
print("=" * 60)
print("  LABEL DISTRIBUTION (vulnerable vs non-vulnerable)")
print("=" * 60)

label_counts = df["target"].value_counts().sort_index()
total_samples = len(df)

for label_value, sample_count in label_counts.items():

    # Decide what to print based on the label value (0 or 1)
    if label_value == 1:
        label_text = "Vulnerable     (1)"
    else:
        label_text = "Non-Vulnerable (0)"

    # Calculate what percentage of the total this label represents
    percentage = (sample_count / total_samples) * 100

    print(f"  {label_text} : {sample_count} samples  ({percentage:.1f}%)")

# ── STEP 9: Show one example of a vulnerable function ─────────────────────────
# df[df["target"] == 1]  filters to only vulnerable rows.
# .iloc[0]               selects the very first one.

print()
print("=" * 60)
print("  EXAMPLE: VULNERABLE FUNCTION  (label = 1)")
print("=" * 60)

vulnerable_example = df[df["target"] == 1].iloc[0]

print(f"  Project   : {vulnerable_example['project']}")
print(f"  Commit ID : {vulnerable_example['commit_id']}")
print(f"  Label     : {vulnerable_example['target']}  ← vulnerable")
print()
print("  Code (first 400 characters):")
print("  " + "-" * 50)

# Print only first 400 characters so the output stays readable
code_preview = vulnerable_example["func"][:400]
for line in code_preview.split("\n"):
    print("  " + line)

print("  ... (truncated)")

# ── STEP 10: Show one example of a non-vulnerable function ────────────────────
# Same as above but we filter to target == 0 (non-vulnerable).

print()
print("=" * 60)
print("  EXAMPLE: NON-VULNERABLE FUNCTION  (label = 0)")
print("=" * 60)

safe_example = df[df["target"] == 0].iloc[0]

print(f"  Project   : {safe_example['project']}")
print(f"  Commit ID : {safe_example['commit_id']}")
print(f"  Label     : {safe_example['target']}  ← non-vulnerable")
print()
print("  Code (first 400 characters):")
print("  " + "-" * 50)

code_preview = safe_example["func"][:400]
for line in code_preview.split("\n"):
    print("  " + line)

print("  ... (truncated)")

# ── STEP 11: Show project distribution ────────────────────────────────────────
# The Devign dataset comes from two projects: FFmpeg and QEMU.
# value_counts() tells us how many functions came from each project.

print()
print("=" * 60)
print("  PROJECT DISTRIBUTION")
print("=" * 60)

project_counts = df["project"].value_counts()

for project_name, count in project_counts.items():
    percentage = (count / total_samples) * 100
    print(f"  {project_name:<10} : {count} samples  ({percentage:.1f}%)")

# ── STEP 12: Show average function length ─────────────────────────────────────
# We calculate how many characters the average C function has.
# This gives us a rough idea of the size/complexity of the code.

print()
print("=" * 60)
print("  FUNCTION LENGTH STATISTICS (in characters)")
print("=" * 60)

df["func_length"] = df["func"].str.len()   # count characters in each function

print(f"  Shortest function : {df['func_length'].min()} characters")
print(f"  Longest function  : {df['func_length'].max()} characters")
print(f"  Average length    : {df['func_length'].mean():.0f} characters")
print(f"  Median length     : {df['func_length'].median():.0f} characters")

# ── DONE ──────────────────────────────────────────────────────────────────────

print()
print("=" * 60)
print("  EXPLORATION COMPLETE")
print("=" * 60)
print("  All findings above will be saved in:")
print("  dataset/notes/dataset_summary.md")
print()
