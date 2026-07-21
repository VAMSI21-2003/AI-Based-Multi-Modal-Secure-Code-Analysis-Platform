# =============================================================================
# extract_ast_features.py
# Day 5: Abstract Syntax Tree (AST) Feature Extraction
# Project: Multi-Modal Code Vulnerability Detection Using CodeBERT
# =============================================================================
#
# WHAT IS AN AST?
#   When a compiler reads your C code, it does not treat it as plain text.
#   Instead, it breaks the code into a TREE structure that represents the
#   MEANING and STRUCTURE of the code.
#
#   Example: The line   x = a + b;   becomes a tree like:
#
#       assignment_expression
#       ?-- identifier: x          (left side of =)
#       ?-- binary_expression      (right side of =)
#           ?-- identifier: a
#           ?-- operator: +
#           ?-- identifier: b
#
#   This tree is called the Abstract Syntax Tree (AST).
#   "Abstract" because it removes irrelevant details (spaces, comments)
#   and keeps only the logical structure.
#
# WHY USE AST FOR VULNERABILITY DETECTION?
#   Raw code text treats "if(x>0)" and "if ( x > 0 )" as different.
#   The AST treats them as identical ? both are an if_statement with
#   the same condition. AST features capture the STRUCTURE of code,
#   not its formatting. Vulnerable code tends to have patterns like:
#     - More pointer operations (risk of use-after-free)
#     - Missing bounds checks (deeper nesting without guard conditions)
#     - Integer arithmetic without overflow checks
#
# WHAT THIS SCRIPT DOES:
#   1. Initialises the tree-sitter C parser
#   2. Demonstrates AST parsing on two hand-written C examples
#   3. Loads the cleaned Devign dataset (produced by Day 4)
#   4. Extracts 11 AST structural features from every C function
#   5. Saves the feature table to dataset/processed/devign_ast_features.csv
#   6. Prints a comparison of feature averages for vulnerable vs safe code
#
# FEATURES EXTRACTED:
#   n_functions       - number of function definitions in the code block
#   n_loops           - total loops: for + while + do-while
#   n_if_statements   - number of if / else-if blocks
#   n_assignments     - number of assignment expressions (x = ...)
#   n_returns         - number of return statements
#   n_pointer_ops     - pointer dereferences (*ptr) and pointer declarations
#   n_function_calls  - number of function call expressions
#   n_binary_ops      - arithmetic and comparison operations (+, -, *, ==, <, >)
#   max_depth         - deepest level of nesting in the AST
#   n_total_nodes     - total count of ALL nodes (measures code complexity)
#   n_error_nodes     - nodes tree-sitter could NOT parse (parse quality check)
#
# HOW TO RUN:
#   1. Open VS Code terminal   (Ctrl + backtick)
#   2. Activate venv:          .\venv\Scripts\activate
#   3. Confirm packages:       pip install tree-sitter tree-sitter-c
#   4. Navigate here:          cd src\ast
#   5. Run:                    python extract_ast_features.py
# =============================================================================


# -- SECTION 0: IMPORTS AND PACKAGE CHECKS ------------------------------------
#
# Python's import system loads external libraries here.
# If a library is missing, we print a helpful message instead of crashing.

import os                        # file paths and folder operations
import sys                       # exit() and sys.argv
import json                      # reading JSON files
from collections import defaultdict  # dictionary that returns 0 for missing keys

import pandas as pd              # tabular data operations

# tree-sitter: the library that parses C code into an AST
try:
    from tree_sitter import Language, Parser
except ImportError:
    print("ERROR: 'tree-sitter' is not installed.")
    print("Please run:  pip install tree-sitter tree-sitter-c")
    sys.exit(1)

# tree-sitter-c: the C language grammar rules for tree-sitter
try:
    import tree_sitter_c as tsc
except ImportError:
    print("ERROR: 'tree-sitter-c' is not installed.")
    print("Please run:  pip install tree-sitter-c")
    sys.exit(1)


# -- SECTION 1: CONSTANTS ------------------------------------------------------
#
# FEATURE_NODE_MAP tells the script which tree-sitter node types map
# to which feature name.
#
# Example: to count "loops", we count nodes of type "for_statement",
#          "while_statement", and "do_statement" and sum them together.
#
# These type strings come from the official tree-sitter C grammar:
#   https://github.com/tree-sitter/tree-sitter-c/blob/master/grammar.js

FEATURE_NODE_MAP = {
    "n_functions"      : ["function_definition"],
    "n_loops"          : ["for_statement", "while_statement", "do_statement"],
    "n_if_statements"  : ["if_statement"],
    "n_assignments"    : ["assignment_expression"],
    "n_returns"        : ["return_statement"],
    "n_pointer_ops"    : ["pointer_expression", "pointer_declarator"],
    "n_function_calls" : ["call_expression"],
    "n_binary_ops"     : ["binary_expression"],
}

# Node types that indicate tree-sitter failed to understand that part of the code
ERROR_NODE_TYPES = {"ERROR", "MISSING"}

# Ignore functions shorter than this (reuse Day 4 threshold)
MIN_FUNC_LENGTH = 50


# -- SECTION 2: PATH SETUP -----------------------------------------------------
#
# We build all file paths relative to THIS script's own location.
# This means the script works regardless of which folder you run it from.

# os.path.abspath(__file__) -> full path of this script
# os.path.dirname(...)      -> folder containing the script
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))

# Go up two levels:  src/ast/ -> src/ -> project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

PROCESSED_DIR = os.path.join(PROJECT_ROOT, "dataset", "processed")
NOTES_DIR     = os.path.join(PROJECT_ROOT, "dataset", "notes")

# Input: cleaned Devign CSV from Day 4
INPUT_CSV  = os.path.join(PROCESSED_DIR, "devign_cleaned.csv")

# Output: same data plus AST feature columns
OUTPUT_CSV = os.path.join(PROCESSED_DIR, "devign_ast_features.csv")


# -- SECTION 3: UTILITY FUNCTIONS ----------------------------------------------

def section(title):
    """Prints a clearly visible section header to organise the terminal output."""
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


def print_tree(node, indent=0, max_depth=3):
    """
    Prints the first few levels of an AST tree so you can see its structure.

    Parameters:
        node      : a tree-sitter Node object
        indent    : how many spaces to indent (increases with each level)
        max_depth : stop printing below this depth (prevents huge output)
    """
    if indent > max_depth:
        return

    # node.type is the grammar rule name  (e.g. "for_statement", "identifier")
    # node.text is the raw source text for this node (bytes -> decoded to string)
    try:
        text_preview = node.text.decode("utf-8")[:40].replace("\n", " ")
    except Exception:
        text_preview = ""

    prefix     = "    " * indent          # indentation
    is_named   = "*" if node.is_named else "-"  # named nodes are meaningful
    print(f"  {prefix}{is_named} [{node.type}]  {text_preview}")

    for child in node.children:
        print_tree(child, indent + 1, max_depth)


# -- SECTION 4: CORE AST TRAVERSAL FUNCTIONS -----------------------------------

def traverse_and_count(node, counts, depth=0, max_depth_ref=None):
    """
    Recursively walks EVERY node in the AST tree (depth-first traversal).

    Depth-first means: go as deep as possible along one branch before
    backtracking and visiting other branches.

    Parameters:
        node          : current node being visited
        counts        : defaultdict(int) ? accumulates counts of each node type
        depth         : how deep we currently are (root = depth 0)
        max_depth_ref : a list containing one integer ? we use a list because
                        Python integers are immutable, so we cannot update a
                        plain int from inside a recursive call.
                        A list IS mutable, so changes persist.
    """
    if max_depth_ref is None:
        max_depth_ref = [0]

    # Update maximum depth if current depth is deeper than previously seen
    if depth > max_depth_ref[0]:
        max_depth_ref[0] = depth

    # Count this node's type  (e.g. adds 1 to counts["for_statement"])
    counts[node.type] += 1

    # Visit every child of this node (recursion)
    for child in node.children:
        traverse_and_count(child, counts, depth + 1, max_depth_ref)

    return max_depth_ref[0]   # return final maximum depth


def extract_ast_features(code_string):
    """
    Takes a C function as a plain string and returns a dictionary of features.

    This is the MAIN function of the script.
    It is called once per Devign sample (once per C function).

    Steps inside:
        1. Convert string -> bytes   (tree-sitter requires bytes)
        2. Parse bytes -> AST tree
        3. Traverse tree -> count all node types
        4. Map node type counts -> feature names
        5. Return feature dictionary

    Parameters:
        code_string (str) : the C source code of one function

    Returns:
        dict : feature names mapped to integer counts
    """

    # -- Parse the code into an AST ------------------------------------------
    # .encode("utf-8") converts Python str -> bytes object
    # parser.parse(bytes) -> a Tree object
    # tree.root_node -> the top-level node of the AST
    try:
        code_bytes = code_string.encode("utf-8")
        tree       = parser.parse(code_bytes)
        root_node  = tree.root_node
    except Exception as error:
        # If something goes wrong, return all-zero features
        print(f"  Warning: parse exception ? {error}")
        return {key: 0 for key in FEATURE_NODE_MAP} | {
            "max_depth"    : 0,
            "n_total_nodes": 0,
            "n_error_nodes": 0,
            "parse_failed" : True,
        }

    # -- Traverse the tree and count every node type --------------------------
    node_counts  = defaultdict(int)   # counts["for_statement"] -> integer
    max_depth_ref = [0]               # mutable container for max depth
    traverse_and_count(root_node, node_counts, 0, max_depth_ref)

    max_depth     = max_depth_ref[0]
    n_total_nodes = sum(node_counts.values())   # sum of ALL node counts

    # Count ERROR nodes (parts tree-sitter could not understand)
    n_error_nodes = sum(
        count for node_type, count in node_counts.items()
        if node_type in ERROR_NODE_TYPES
    )

    # -- Build the named feature dictionary -----------------------------------
    features = {}

    for feature_name, node_type_list in FEATURE_NODE_MAP.items():
        # Sum counts for all node types that belong to this feature
        # e.g. n_loops = counts["for_statement"] +
        #                counts["while_statement"] +
        #                counts["do_statement"]
        features[feature_name] = sum(
            node_counts[node_type] for node_type in node_type_list
        )

    features["max_depth"]     = max_depth
    features["n_total_nodes"] = n_total_nodes
    features["n_error_nodes"] = n_error_nodes
    features["parse_failed"]  = False

    return features


# -- SECTION 5: INITIALIZE THE C PARSER ---------------------------------------

section("STEP 1: INITIALISING TREE-SITTER C PARSER")

# Language(tsc.language()) loads the C grammar rules from tree-sitter-c package.
# Think of it as loading a "dictionary of C syntax rules".
#
# Parser(C_LANGUAGE) creates a parser that USES those rules to read C code.
# This is the object we call .parse() on for every Devign sample.

try:
    C_LANGUAGE = Language(tsc.language())
    parser     = Parser(C_LANGUAGE)
    print("  C parser initialised successfully.")
except Exception as e:
    print(f"  ERROR: {e}")
    print("  Try: pip install --upgrade tree-sitter tree-sitter-c")
    sys.exit(1)


# -- SECTION 6: DEMO ? PARSE TWO SAMPLE FUNCTIONS AND PRINT THE AST -----------

section("STEP 2: DEMO ? PARSING SAMPLE C FUNCTIONS")

# -- Sample A: Vulnerable function (Buffer Overflow ? missing upper bound check) --
SAMPLE_VULNERABLE = """\
static int hq_decode_frame(AVCodecContext *avctx, AVFrame *frame,
                            const uint8_t *src, int src_size)
{
    uint8_t buf[1024];
    int i;
    int result;

    if (src_size <= 0)
        return AVERROR_INVALIDDATA;

    for (i = 0; i < src_size; i++) {
        buf[i] = src[i] ^ 0xFF;
    }

    if (avctx->extradata_size > 0) {
        result = process_header(avctx);
        if (result < 0)
            return result;
    }

    return process_frame(avctx, frame, buf, src_size);
}"""

# -- Sample B: Non-Vulnerable version (upper bound check added) --
SAMPLE_SAFE = """\
static int hq_decode_frame(AVCodecContext *avctx, AVFrame *frame,
                            const uint8_t *src, int src_size)
{
    uint8_t buf[1024];
    int i;
    int result;

    if (src_size <= 0 || src_size > (int)sizeof(buf))
        return AVERROR_INVALIDDATA;

    for (i = 0; i < src_size; i++) {
        buf[i] = src[i] ^ 0xFF;
    }

    if (avctx->extradata_size > 0) {
        result = process_header(avctx);
        if (result < 0)
            return result;
    }

    return process_frame(avctx, frame, buf, src_size);
}"""

# Process each sample and print results
demo_results = {}

for label, code, title in [
    (1, SAMPLE_VULNERABLE, "VULNERABLE  (label = 1) ? Buffer Overflow"),
    (0, SAMPLE_SAFE,       "NON-VULNERABLE  (label = 0) ? Safe Version"),
]:
    print()
    print(f"  -- {title} --")
    print()

    # Parse and print the top 3 levels of the AST (for learning purposes)
    code_bytes = code.encode("utf-8")
    tree       = parser.parse(code_bytes)
    print("  AST STRUCTURE (top 3 levels only):")
    print("  * = named node (meaningful)    - = anonymous node (punctuation)")
    print()
    print_tree(tree.root_node, indent=0, max_depth=3)

    # Extract and print features
    features = extract_ast_features(code)
    demo_results[label] = features

    print()
    print("  EXTRACTED FEATURES:")
    print(f"  {'Feature':<25} {'Value':>6}")
    print(f"  {'-'*33}")
    for key, val in features.items():
        if key != "parse_failed":
            print(f"  {key:<25} {val:>6}")

# -- Print comparison of the two samples --
print()
print("  -- FEATURE COMPARISON: VULNERABLE vs SAFE --")
print()
print(f"  {'Feature':<25} {'Vulnerable':>12} {'Safe':>8} {'Same?':>8}")
print(f"  {'-'*57}")
for key in demo_results[1]:
    if key == "parse_failed":
        continue
    v = demo_results[1][key]
    s = demo_results[0][key]
    same = "YES" if v == s else "DIFFERS"
    print(f"  {key:<25} {v:>12} {s:>8} {same:>8}")

print()
print("  KEY INSIGHT:")
print("  Both functions have the same AST structure EXCEPT for")
print("  n_binary_ops and max_depth ? the safe version adds one")
print("  extra comparison ( || src_size > sizeof(buf) ) which the")
print("  model should learn to associate with SAFE code.")


# -- SECTION 7: LOAD THE CLEANED DEVIGN DATASET -------------------------------

section("STEP 3: LOADING CLEANED DEVIGN DATASET")

if not os.path.exists(INPUT_CSV):
    print(f"  WARNING: Cleaned dataset not found at:")
    print(f"    {INPUT_CSV}")
    print()
    print("  To process the full dataset, first run Day 4's script:")
    print("    cd src\\preprocessing")
    print("    python preprocess_dataset.py")
    print()
    print("  The DEMO above was completed successfully.")
    print("  Skipping full-dataset processing.")
    sys.exit(0)

df = pd.read_csv(INPUT_CSV, encoding="utf-8")

print(f"  File loaded : {INPUT_CSV}")
print(f"  Samples     : {len(df)}")
print(f"  Columns     : {list(df.columns)}")


# -- SECTION 8: EXTRACT AST FEATURES FOR EVERY SAMPLE -------------------------

section("STEP 4: EXTRACTING AST FEATURES FROM ALL SAMPLES")

print("  This will take a few minutes for ~27,000 functions.")
print("  Progress is shown every 1,000 samples.")
print()

feature_rows = []   # will collect one dict per sample
failed_count = 0    # number of samples where parsing produced errors
short_count = 0     # informational only -- rows under MIN_FUNC_LENGTH are still kept (Phase 4 fix)

if "original_id" not in df.columns:
    print("  ERROR: input file has no 'original_id' column.")
    print("  Re-run src/preprocessing/preprocess_dataset.py (Day 4) first --")
    print("  it must be regenerated to assign this stable ID (see")
    print("  docs/ML_FORENSIC_AUDIT_PHASE4.md for why this is required).")
    sys.exit(1)

for row_index, row in df.iterrows():

    # -- Progress display ------------------------------------------------------
    # end="\r" overwrites the same terminal line instead of printing new lines
    if row_index % 1000 == 0:
        pct = (row_index / len(df)) * 100
        print(f"  [{pct:5.1f}%]  Processed {row_index:6d} / {len(df)} samples...",
              end="\r")

    # -- Get the C source code for this row -----------------------------------
    code_text = str(row["func"])

    # NOTE (Phase 4 fix): this script used to `continue` (silently drop the
    # row) here if the function was under MIN_FUNC_LENGTH characters. That
    # was a SEPARATE, stricter filter than extract_metrics.py's (10 chars),
    # and since each script used to assign sample_id = its own output's row
    # position, the two scripts' numbering silently diverged the moment
    # either one dropped a row the other kept -- confirmed to affect 99.35%
    # of the fused dataset (docs/ML_FORENSIC_AUDIT_PHASE4.md). Every row is
    # now KEPT and carried through with its stable original_id; a genuinely
    # too-short/unparseable function still gets real (usually all-zero,
    # parse_failed=True) features via extract_ast_features()'s own
    # exception handling below, rather than silently vanishing from the
    # dataset and shifting every subsequent row's alignment.
    ast_feats = extract_ast_features(code_text)

    if ast_feats["parse_failed"]:
        failed_count += 1
    if len(code_text.strip()) < MIN_FUNC_LENGTH:
        short_count += 1  # informational only -- row is still kept, see note above

    # -- Build the output row --------------------------------------------------
    # Start with the original columns then add AST feature columns
    combined = {
        "original_id": row["original_id"],
        "func"      : row["func"],
        "target"    : row["target"],
        "project"   : row.get("project",   "unknown"),
        "commit_id" : row.get("commit_id", "unknown"),
    }
    combined.update(ast_feats)   # merge AST features into the dict
    feature_rows.append(combined)

# Print a blank line after the progress display
print(f"\n  Done.  Processed {len(feature_rows)} samples.  (Every input row is kept --")
print(f"  no row is dropped by this script; see Phase 4 fix notes above.)")
print(f"  Samples with parse errors      : {failed_count}")
print(f"  Parse error rate               : {failed_count/len(feature_rows)*100:.2f}%")
print(f"  Samples under {MIN_FUNC_LENGTH} chars (kept anyway) : {short_count}")


# -- SECTION 9: SAVE FEATURES TO CSV ------------------------------------------

section("STEP 5: SAVING AST FEATURE TABLE")

os.makedirs(PROCESSED_DIR, exist_ok=True)

features_df = pd.DataFrame(feature_rows)
features_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")

print(f"  Saved: {OUTPUT_CSV}")
print(f"  Rows   : {len(features_df)}")
print(f"  Columns: {len(features_df.columns)}")
print()
print("  Column list:")
for col in features_df.columns:
    dtype = str(features_df[col].dtype)
    print(f"    {col:<25}  ({dtype})")


# -- SECTION 10: STATISTICS ? VULNERABLE vs NON-VULNERABLE --------------------

section("STEP 6: FEATURE STATISTICS ? VULNERABLE vs NON-VULNERABLE")

vuln_df     = features_df[features_df["target"] == 1]
non_vuln_df = features_df[features_df["target"] == 0]

print(f"  Vulnerable samples     : {len(vuln_df)}")
print(f"  Non-Vulnerable samples : {len(non_vuln_df)}")
print()

# Print one row per feature: mean for vulnerable, mean for safe, and the difference
feature_cols = [c for c in features_df.columns
                if c.startswith("n_") or c == "max_depth"]

print(f"  {'Feature':<25} {'Vuln Avg':>10} {'Safe Avg':>10} {'Diff':>10}  Interpretation")
print(f"  {'-'*80}")

for col in feature_cols:
    if col in ("n_error_nodes",):
        continue
    v_mean  = vuln_df[col].mean()
    s_mean  = non_vuln_df[col].mean()
    diff    = v_mean - s_mean
    sign    = "+" if diff >= 0 else ""
    interp  = "more in vuln" if diff > 0.1 else ("more in safe" if diff < -0.1 else "similar")
    print(f"  {col:<25} {v_mean:>10.2f} {s_mean:>10.2f} {sign}{diff:>9.2f}  {interp}")


# -- SECTION 11: DONE ----------------------------------------------------------

section("AST FEATURE EXTRACTION COMPLETE")
print(f"  Input  : {INPUT_CSV}")
print(f"  Output : {OUTPUT_CSV}")
print()
print("  What to do next:")
print("    Day 6 ? CodeBERT text feature extraction")
print("    Day 7 ? Combine AST features + CodeBERT features")
print("    Day 8 ? Train the multi-modal classifier")
print()
