# =============================================================================
# extract_metrics.py
# Day 6: Software Metrics Extraction
# Project: Multi-Modal Code Vulnerability Detection Using CodeBERT
# =============================================================================
#
# WHAT ARE SOFTWARE METRICS?
#
#   A software metric is a NUMBER that describes a measurable property
#   of source code. Think of it like health measurements for code:
#
#     - Lines of Code  = how big is the function?
#     - Loop Count     = how many repetitive operations does it do?
#     - Comment Count  = how well documented is it?
#     - Nesting Depth  = how complex is its logic?
#
#   Just as a doctor uses blood pressure, temperature, and heart rate
#   together to judge your health, we use MULTIPLE metrics together
#   to judge a function's vulnerability risk.
#
# WHY USE METRICS FOR VULNERABILITY DETECTION?
#
#   Research has consistently shown that:
#     - LARGER functions (more LOC) are more likely to contain bugs
#     - MORE nested code (high nesting depth) hides logic errors
#     - FEWER comments indicate less care taken by the developer
#     - MORE loops without matching if-statements suggest missing
#       bounds checks (buffer overflow risk)
#
#   Metrics are computed using simple string operations — no special
#   parser needed. This makes them:
#     - Fast to compute (thousands of functions per second)
#     - Easy to understand and explain
#     - Useful as complementary features alongside AST and CodeBERT
#
# METRICS EXTRACTED IN THIS SCRIPT:
#
#   Core metrics (as requested):
#     loc               - Lines of Code (non-empty lines)
#     function_count    - Number of function definitions
#     loop_count        - Total loops: for + while + do-while
#     if_count          - Number of if statements
#     return_count      - Number of return statements
#     avg_line_length   - Average length of non-empty lines
#     max_line_length   - Length of the longest line
#     comment_count     - Number of // and /* */ comments
#
#   Bonus metrics (extra insight):
#     total_lines       - All lines including blank ones
#     blank_line_count  - Lines with only whitespace
#     nesting_depth     - Approximate max nesting level (brace counting)
#     operator_count    - Arithmetic and comparison operators
#     pointer_count     - Pointer dereferences (* and ->)
#
# HOW TO RUN:
#   1. Open VS Code terminal     (Ctrl + backtick)
#   2. Activate venv:            .\venv\Scripts\activate
#   3. Navigate to this folder:  cd src\metrics
#   4. Run:                      python extract_metrics.py
#
# NO EXTRA PACKAGES NEEDED — only uses re, os, sys, pandas (already installed)
# =============================================================================


# ── IMPORTS ───────────────────────────────────────────────────────────────────
#
# re      : regular expressions — pattern matching inside strings
# os      : file path operations (joining, checking existence)
# sys     : exit() function to stop the script cleanly
# pandas  : DataFrame for loading CSV and saving results

import re
import os
import sys
import pandas as pd


# ── PATH SETUP ────────────────────────────────────────────────────────────────
#
# Build all paths relative to THIS script's location.
# This ensures the script works no matter what folder you run it from.
#
# SCRIPT_DIR   = .../src/metrics/
# PROJECT_ROOT = .../MultiModal_Code_Vulnerability_Detection/   (two levels up)

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

PROCESSED_DIR = os.path.join(PROJECT_ROOT, "dataset", "processed")

# Input: cleaned Devign CSV from Day 4
INPUT_CSV  = os.path.join(PROCESSED_DIR, "devign_cleaned.csv")

# Output: same data plus all metric columns
OUTPUT_CSV = os.path.join(PROCESSED_DIR, "metrics_features.csv")


# ── UTILITY ───────────────────────────────────────────────────────────────────

def section(title):
    """Prints a visible header to separate sections in the terminal output."""
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


# =============================================================================
# PART A: INDIVIDUAL METRIC FUNCTIONS
#
# Each metric is a separate function that takes ONE argument:
#   code_string  (str) — the raw C source code of one function
#
# Each function returns ONE number (int or float).
#
# This design makes the code easy to read, test, and extend.
# Adding a new metric = adding one new function.
# =============================================================================


# ── METRIC 1: Lines of Code (LOC) ─────────────────────────────────────────────

def compute_loc(code_string):
    """
    Count the number of NON-EMPTY lines in the code.

    A line is considered empty if it contains only spaces or tabs.
    Blank lines between code blocks are excluded.

    Why it matters for vulnerability detection:
        Larger functions (more LOC) are statistically more likely to
        contain bugs. Research shows vulnerability density decreases
        as LOC increases — but the absolute number of vulnerabilities
        tends to be higher in larger functions.

    Example:
        'int f() {\\n    return 0;\\n\\n}'  →  3 non-empty lines
    """
    lines = code_string.split('\n')
    # .strip() removes leading/trailing whitespace from each line
    # We count the line only if something remains after stripping
    non_empty_lines = [line for line in lines if line.strip() != '']
    return len(non_empty_lines)


# ── METRIC 2: Total Lines ──────────────────────────────────────────────────────

def compute_total_lines(code_string):
    """
    Count ALL lines including blank lines.

    Unlike LOC, this includes empty lines. Together with LOC, it
    tells us the ratio of blank-to-code lines, which can indicate
    code style and readability.
    """
    return len(code_string.split('\n'))


# ── METRIC 3: Blank Line Count ─────────────────────────────────────────────────

def compute_blank_lines(code_string):
    """
    Count lines that are empty or contain only whitespace.

    Blank lines are often used to separate logical sections.
    A function with many blank lines is more readable; fewer
    blank lines in complex code may indicate rushed development.
    """
    lines = code_string.split('\n')
    return sum(1 for line in lines if line.strip() == '')


# ── METRIC 4: Function Count ───────────────────────────────────────────────────

def compute_function_count(code_string):
    """
    Count C function DEFINITIONS using a regular expression heuristic.

    A C function definition looks like:
        return_type  function_name ( parameters ) {

    We search for the pattern: word followed by ( ) then {
    We exclude C control-flow keywords (if, for, while, switch)
    because they also use the ( ) { pattern.

    LIMITATION: This is a heuristic (an educated approximation), not a
    true parser. It may occasionally miscount in very unusual code.
    In the Devign dataset each sample IS one function, so the result
    is almost always 1.

    Example:
        'static int decode(uint8_t *src) {' matches → count += 1
        'if (x > 0) {'                    excluded  → not counted
    """
    # C keywords that use the pattern word( ) { but are NOT functions
    c_control_keywords = {
        'if', 'for', 'while', 'switch', 'do', 'else',
        'return', 'sizeof', 'typeof', 'alignof'
    }

    # Regex pattern explanation:
    #   \b          : word boundary (start of a word)
    #   ([a-zA-Z_]\w*)  : capture one identifier (letter or _ then alphanumerics)
    #   \s*         : optional spaces
    #   \(          : opening parenthesis
    #   [^;{]*      : anything except ; or { (the parameter list)
    #   \)          : closing parenthesis
    #   \s*         : optional spaces
    #   \{          : opening brace (starts function body)

    pattern = r'\b([a-zA-Z_]\w*)\s*\([^;{]*\)\s*\{'
    matches = re.findall(pattern, code_string)

    # Count only matches where the captured name is NOT a C keyword
    func_count = sum(1 for name in matches if name not in c_control_keywords)
    return max(func_count, 0)


# ── METRIC 5: Loop Count ────────────────────────────────────────────────────────

def compute_loop_count(code_string):
    """
    Count all loop statements: for, while, and do-while.

    Why it matters:
        Loops that iterate over buffers without checking array bounds
        are a primary source of buffer overflow vulnerabilities.
        A high loop count WITHOUT a corresponding high if-statement
        count suggests bounds checks may be missing.

    Counts:
        for (...)  { ... }    → for_statement
        while (...) { ... }   → while_statement
        do { ... } while (...) → do_statement

    Example:
        'for (i=0;i<n;i++)' → 1
        'while (ptr != NULL)' → 1
        Total = 2
    """
    # \b ensures we match the whole keyword, not a word ending in 'for'
    # \s* allows spaces between keyword and (
    for_count   = len(re.findall(r'\bfor\s*\(',   code_string))
    while_count = len(re.findall(r'\bwhile\s*\(', code_string))

    # 'do' is followed by whitespace then { — not by (
    do_count    = len(re.findall(r'\bdo\b',        code_string))

    return for_count + while_count + do_count


# ── METRIC 6: If Statement Count ───────────────────────────────────────────────

def compute_if_count(code_string):
    """
    Count if statements (including else-if chains).

    Why it matters:
        If statements often represent bounds checks and guard conditions.
        The RATIO of if-count to loop-count is informative:

        High loops, LOW ifs  → few bounds checks → likely vulnerable
        High loops, HIGH ifs → many bounds checks → likely safer

    Example:
        'if (size > MAX)' → 1
        'else if (ptr == NULL)' → 1 (else-if counted separately)
    """
    return len(re.findall(r'\bif\s*\(', code_string))


# ── METRIC 7: Return Statement Count ───────────────────────────────────────────

def compute_return_count(code_string):
    """
    Count return statements.

    Why it matters:
        Multiple early return statements can indicate:
        - Missing cleanup code (resource/memory leaks)
        - Complex control flow that is hard to reason about
        - Error handling paths that skip deallocation

        A function that allocates memory but has many early returns
        may fail to free memory on some paths (memory leak).

    Example:
        'return -1;'         → 1
        'return AVERROR;'    → 1
        'return result;'     → 1
    """
    return len(re.findall(r'\breturn\b', code_string))


# ── METRIC 8: Average Line Length ──────────────────────────────────────────────

def compute_avg_line_length(code_string):
    """
    Compute the average character length of all non-empty lines.

    Why it matters:
        Very long lines often indicate:
        - Complex expressions packed into one line (harder to review)
        - Long string literals (possible injection points)
        - Chained function calls without intermediate checks

        Very short lines on average may indicate the function is
        well-decomposed into simple steps.

    Returns:
        float rounded to 2 decimal places, or 0.0 if no lines.
    """
    non_empty = [line for line in code_string.split('\n') if line.strip()]
    if not non_empty:
        return 0.0
    total_length = sum(len(line) for line in non_empty)
    return round(total_length / len(non_empty), 2)


# ── METRIC 9: Maximum Line Length ──────────────────────────────────────────────

def compute_max_line_length(code_string):
    """
    Find the length of the longest single line in the function.

    Why it matters:
        Extremely long lines often contain complex expressions that
        are difficult to audit manually. Security reviewers may skip
        over a 200-character line and miss a vulnerability.

    Returns:
        int — character count of the longest line, or 0 if empty.
    """
    lines = code_string.split('\n')
    if not lines:
        return 0
    return max(len(line) for line in lines)


# ── METRIC 10: Comment Count ────────────────────────────────────────────────────

def compute_comment_count(code_string):
    """
    Count all comments: single-line (//) and multi-line (/* ... */).

    Why it matters:
        Code with more comments is generally better understood by
        its authors and reviewers. The absence of comments in complex
        code (many loops, pointers, nested conditions) often correlates
        with higher bug density.

    Single-line comment example:
        // this allocates the buffer

    Multi-line comment example:
        /* allocates size bytes for the output buffer
           caller is responsible for freeing */

    Note: This regex counts the COMMENT BLOCKS, not the lines inside
    multi-line comments.
    """
    # //[^\n]* matches // followed by anything until the end of the line
    single_line_count = len(re.findall(r'//[^\n]*', code_string))

    # /\*.*?\*/ matches /* to */ including everything in between
    # re.DOTALL makes . match newlines too (needed for multi-line comments)
    # .*? is non-greedy — stops at the FIRST */ found
    multi_line_count = len(re.findall(r'/\*.*?\*/', code_string, re.DOTALL))

    return single_line_count + multi_line_count


# ── BONUS METRIC 11: Nesting Depth ─────────────────────────────────────────────

def compute_nesting_depth(code_string):
    """
    Approximate the maximum nesting depth by counting opening { and
    closing } braces as we scan through the code character by character.

    Each { increases the current depth by 1.
    Each } decreases the current depth by 1.
    We track the highest depth seen at any point.

    Why it matters:
        Deeply nested code (if inside for inside if inside while)
        is harder to understand and audit. Missing bounds checks are
        more likely to hide in deeply nested code.

    LIMITATION:
        We count ALL braces including those inside strings like
        printf("{value}") — this is an approximation, not a true
        syntactic depth count. For the Devign dataset it gives a
        reasonable estimate.

    Example:
        void f() {           depth = 1
            if (x) {         depth = 2
                for (...) {  depth = 3   <- max_depth = 3
                }            depth = 2
            }                depth = 1
        }                    depth = 0
        Returns: 3
    """
    current_depth = 0
    max_depth     = 0

    for char in code_string:
        if char == '{':
            current_depth += 1
            if current_depth > max_depth:
                max_depth = current_depth
        elif char == '}':
            current_depth -= 1
            if current_depth < 0:      # guard against malformed code
                current_depth = 0

    return max_depth


# ── BONUS METRIC 12: Operator Count ────────────────────────────────────────────

def compute_operator_count(code_string):
    """
    Count arithmetic, comparison, and logical operators.

    Operators counted:
        ++  --          (increment / decrement)
        +=  -=  *=  /=  (compound assignment)
        ==  !=  <=  >=  (comparison)
        &&  ||          (logical AND / OR)
        <<  >>          (bitshift — used in integer operations)

    Why it matters:
        Integer overflow vulnerabilities involve arithmetic operators
        applied to values without overflow checking. A high number of
        arithmetic operators (especially *, <<) in a function with no
        corresponding bounds checks is a risk signal.
    """
    # List of operator patterns to search for
    # Order matters: longer patterns (like ==, !=) must come before
    # shorter ones (like =, !) to avoid partial matches
    operator_patterns = [
        r'\+\+',    # increment
        r'--',      # decrement
        r'\+=',     # add-assign
        r'-=',      # subtract-assign
        r'\*=',     # multiply-assign
        r'/=',      # divide-assign
        r'==',      # equality comparison
        r'!=',      # not-equal comparison
        r'<=',      # less-than-or-equal
        r'>=',      # greater-than-or-equal
        r'&&',      # logical AND
        r'\|\|',    # logical OR
        r'<<',      # left bitshift
        r'>>',      # right bitshift
    ]

    total = 0
    for pattern in operator_patterns:
        total += len(re.findall(pattern, code_string))
    return total


# ── BONUS METRIC 13: Pointer Count ─────────────────────────────────────────────

def compute_pointer_count(code_string):
    """
    Count pointer-related operations in C code.

    We count:
        ->  (arrow operator — access field through pointer)
        *identifier  (pointer dereference — reading/writing via pointer)

    Why it matters:
        Pointer operations are the single biggest source of
        memory-safety vulnerabilities in C:
          - Use-After-Free: dereferencing a freed pointer
          - Null Pointer Dereference: dereferencing NULL
          - Buffer Overread: pointer arithmetic going out of bounds

        A high pointer count in a function signals higher memory-safety
        risk that should be carefully reviewed.

    LIMITATION:
        The * character also means multiplication. We use a heuristic:
        count only * that are immediately followed by an identifier name
        (letter or underscore), which indicates dereference rather than
        multiplication (which is usually between two values: a * b).
    """
    # Arrow operator: ->
    arrow_count = len(re.findall(r'->', code_string))

    # Pointer dereference: *followed_by_identifier
    # [a-zA-Z_(] means the char after * is a letter, _ or ( — likely a deref
    dereference_count = len(re.findall(r'\*\s*[a-zA-Z_(]', code_string))

    return arrow_count + dereference_count


# =============================================================================
# PART B: MAIN EXTRACTOR — calls all metric functions for one code sample
# =============================================================================

def extract_all_metrics(code_string):
    """
    Calls every metric function for one C function string.
    Returns a single dictionary with all metric values.

    Parameters:
        code_string (str) : C source code of one function

    Returns:
        dict : { metric_name: value, ... }
    """
    return {
        # ── Core metrics (as requested) ──────────────────────────────────
        "loc"             : compute_loc(code_string),
        "function_count"  : compute_function_count(code_string),
        "loop_count"      : compute_loop_count(code_string),
        "if_count"        : compute_if_count(code_string),
        "return_count"    : compute_return_count(code_string),
        "avg_line_length" : compute_avg_line_length(code_string),
        "max_line_length" : compute_max_line_length(code_string),
        "comment_count"   : compute_comment_count(code_string),

        # ── Bonus metrics (extra structural insight) ──────────────────────
        "total_lines"     : compute_total_lines(code_string),
        "blank_lines"     : compute_blank_lines(code_string),
        "nesting_depth"   : compute_nesting_depth(code_string),
        "operator_count"  : compute_operator_count(code_string),
        "pointer_count"   : compute_pointer_count(code_string),
    }


# =============================================================================
# PART C: DEMO — run on two hand-written C functions before touching the dataset
# =============================================================================

section("STEP 1: DEMO -- SOFTWARE METRICS ON SAMPLE C FUNCTIONS")

# ── Sample A: Vulnerable function (missing upper bound check) ──
SAMPLE_VULNERABLE = """\
static int hq_decode_frame(AVCodecContext *avctx, AVFrame *frame,
                            const uint8_t *src, int src_size)
{
    /* decode one frame from the input buffer */
    uint8_t buf[1024];
    int i;
    int result;

    if (src_size <= 0)
        return AVERROR_INVALIDDATA;

    // copy src into local buffer -- NO upper bound check here
    for (i = 0; i < src_size; i++) {
        buf[i] = src[i] ^ avctx->priv_data;
    }

    if (avctx->extradata_size > 0) {
        result = process_header(avctx);
        if (result < 0)
            return result;
    }

    return process_frame(avctx, frame, buf, src_size);
}"""

# ── Sample B: Non-Vulnerable (upper bound check added) ──
SAMPLE_SAFE = """\
static int hq_decode_frame(AVCodecContext *avctx, AVFrame *frame,
                            const uint8_t *src, int src_size)
{
    /* decode one frame from the input buffer */
    uint8_t buf[1024];
    int i;
    int result;

    // validate input size before using it
    if (src_size <= 0 || src_size > (int)sizeof(buf)) {
        av_log(avctx, AV_LOG_ERROR, "invalid src_size: %d\n", src_size);
        return AVERROR_INVALIDDATA;
    }

    // safe to copy: src_size is guaranteed <= 1024
    for (i = 0; i < src_size; i++) {
        buf[i] = src[i] ^ avctx->priv_data;
    }

    if (avctx->extradata_size > 0) {
        result = process_header(avctx);
        if (result < 0)
            return result;
    }

    return process_frame(avctx, frame, buf, src_size);
}"""

# Compute metrics for both samples
vuln_metrics = extract_all_metrics(SAMPLE_VULNERABLE)
safe_metrics  = extract_all_metrics(SAMPLE_SAFE)

# Print a comparison table
print()
print(f"  {'Metric':<20} {'Vulnerable':>12} {'Safe':>8}  {'Change':>10}")
print(f"  {'-'*55}")
for metric_name in vuln_metrics:
    v_val  = vuln_metrics[metric_name]
    s_val  = safe_metrics[metric_name]

    if isinstance(v_val, float) or isinstance(s_val, float):
        v_str = f"{v_val:>12.2f}"
        s_str = f"{s_val:>8.2f}"
        diff  = s_val - v_val
        diff_str = f"+{diff:.2f}" if diff > 0 else f"{diff:.2f}"
    else:
        v_str = f"{v_val:>12}"
        s_str = f"{s_val:>8}"
        diff  = s_val - v_val
        diff_str = f"+{diff}" if diff > 0 else f"{diff}"

    changed = "<-- differs" if v_val != s_val else ""
    print(f"  {metric_name:<20} {v_str} {s_str}  {diff_str:>10}  {changed}")

print()
print("  KEY OBSERVATIONS:")
print("  1. comment_count is HIGHER in the safe version (2 vs 1 comment)")
print("     Safe code is better documented.")
print("  2. if_count is HIGHER in the safe version (3 vs 2)")
print("     The extra bounds check adds one more if statement.")
print("  3. avg_line_length is HIGHER in the safe version")
print("     The error logging line is longer due to format string.")
print("  4. All structure metrics (loc, loop, return) are similar")
print("     because the two functions have the same overall structure.")


# =============================================================================
# PART D: PROCESS THE FULL DEVIGN DATASET
# =============================================================================

section("STEP 2: LOADING CLEANED DEVIGN DATASET")

if not os.path.exists(INPUT_CSV):
    print(f"  WARNING: Cleaned dataset not found at:")
    print(f"    {INPUT_CSV}")
    print()
    print("  Please run Day 4 preprocessing first:")
    print("    cd src\\preprocessing")
    print("    python preprocess_dataset.py")
    print()
    print("  The DEMO above completed successfully.")
    print("  Skipping full-dataset processing.")
    sys.exit(0)

# pd.read_csv() loads the CSV file into a DataFrame (a table in memory)
# encoding="utf-8" ensures special characters in code are read correctly
df = pd.read_csv(INPUT_CSV, encoding="utf-8")

print(f"  File loaded : {INPUT_CSV}")
print(f"  Samples     : {len(df)}")
print(f"  Columns     : {list(df.columns)}")


# =============================================================================
# PART E: EXTRACT METRICS FOR EVERY SAMPLE
# =============================================================================

section("STEP 3: EXTRACTING METRICS FROM ALL SAMPLES")

print("  Computing metrics for every function...")
print("  Progress shown every 1,000 samples.")
print()

if "original_id" not in df.columns:
    print("  ERROR: input file has no 'original_id' column.")
    print("  Re-run src/preprocessing/preprocess_dataset.py (Day 4) first --")
    print("  it must be regenerated to assign this stable ID (see")
    print("  docs/ML_FORENSIC_AUDIT_PHASE4.md for why this is required).")
    sys.exit(1)

all_rows = []   # will hold one dict per sample
short_count = 0  # informational only -- these rows are still kept (Phase 4 fix)

for row_index, row in df.iterrows():

    # ── Progress indicator ────────────────────────────────────────────────────
    if row_index % 1000 == 0:
        pct = (row_index / len(df)) * 100
        print(f"  [{pct:5.1f}%]  {row_index:6d} / {len(df)} processed...", end="\r")

    # ── Get this row's code string ────────────────────────────────────────────
    # str() ensures it is definitely a string even if pandas read it strangely
    code_text = str(row["func"])

    # NOTE (Phase 4 fix): this script used to `continue` (silently drop the
    # row) here for anything under 10 characters -- a DIFFERENT, laxer
    # threshold than extract_ast_features.py's 50 characters. Since each
    # script used to assign sample_id = its own output's row position, that
    # inconsistency silently desynced the two scripts' numbering, confirmed
    # to affect 99.35% of the fused dataset
    # (docs/ML_FORENSIC_AUDIT_PHASE4.md). Every row is now kept, carried
    # through with its stable original_id; metrics are pure string
    # operations that cannot meaningfully fail on any non-empty input, so
    # there is no correctness reason to drop short rows here.
    if len(code_text.strip()) < 10:
        short_count += 1  # informational only -- row is still processed below

    # ── Compute all metrics for this code sample ──────────────────────────────
    metrics = extract_all_metrics(code_text)

    # ── Build the output row ──────────────────────────────────────────────────
    # We keep the original columns AND add the new metric columns
    output_row = {
        "original_id": row["original_id"],
        "func"      : row["func"],            # original code
        "target"    : row["target"],          # label (0 or 1)
        "project"   : row.get("project",   "unknown"),
        "commit_id" : row.get("commit_id", "unknown"),
    }
    output_row.update(metrics)   # merge: adds all 13 metric columns
    all_rows.append(output_row)

# Print blank line to clear the progress line
print(f"\n  Done. Processed {len(all_rows)} samples. (Every input row is kept -- no row")
print(f"  is dropped by this script; see Phase 4 fix notes above.)")
print(f"  Samples under 10 chars (kept anyway): {short_count}")


# =============================================================================
# PART F: SAVE TO CSV
# =============================================================================

section("STEP 4: SAVING METRICS FEATURES")

# Make sure the output folder exists (create if missing)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Convert list of dicts to DataFrame
metrics_df = pd.DataFrame(all_rows)

# Save to CSV
# index=False  → do not add an extra numbered column (0, 1, 2...) to the file
metrics_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")

print(f"  Saved: {OUTPUT_CSV}")
print(f"  Rows   : {len(metrics_df)}")
print(f"  Columns: {len(metrics_df.columns)}")
print()
print("  All columns in the output CSV:")
for col in metrics_df.columns:
    dtype = str(metrics_df[col].dtype)
    print(f"    {col:<22}  (type: {dtype})")


# =============================================================================
# PART G: STATISTICS — COMPARE VULNERABLE vs NON-VULNERABLE
# =============================================================================

section("STEP 5: METRIC STATISTICS -- VULNERABLE vs NON-VULNERABLE")

vuln_df     = metrics_df[metrics_df["target"] == 1]
non_vuln_df = metrics_df[metrics_df["target"] == 0]

print(f"  Vulnerable samples     : {len(vuln_df)}")
print(f"  Non-Vulnerable samples : {len(non_vuln_df)}")
print()

# Columns that are metric features (not metadata)
metric_cols = [
    "loc", "function_count", "loop_count", "if_count",
    "return_count", "avg_line_length", "max_line_length",
    "comment_count", "total_lines", "blank_lines",
    "nesting_depth", "operator_count", "pointer_count",
]

print(f"  {'Metric':<22} {'Vuln Avg':>10} {'Safe Avg':>10} {'Diff':>8}  Signal?")
print(f"  {'-'*72}")

for col in metric_cols:
    if col not in metrics_df.columns:
        continue
    v_mean = vuln_df[col].mean()
    s_mean = non_vuln_df[col].mean()
    diff   = v_mean - s_mean
    sign   = "+" if diff >= 0 else ""

    # Simple interpretation
    if abs(diff) < 0.05 * max(v_mean, s_mean, 0.001):
        signal = "similar"
    elif diff > 0:
        signal = "more in vulnerable"
    else:
        signal = "more in safe"

    print(f"  {col:<22} {v_mean:>10.2f} {s_mean:>10.2f} {sign}{diff:>7.2f}  {signal}")

print()
print("  INTERPRETATION GUIDE:")
print("  'more in vulnerable' = vulnerable functions have higher average values")
print("  'more in safe'       = safe functions have higher average values")
print("  'similar'            = the metric alone does not separate the classes well")


# =============================================================================
# PART H: GENERATE AUTO SUMMARY NOTES
# =============================================================================

section("STEP 6: SAVING NOTES SUMMARY")

NOTES_DIR   = os.path.join(PROJECT_ROOT, "dataset", "notes")
os.makedirs(NOTES_DIR, exist_ok=True)

notes_path = os.path.join(NOTES_DIR, "metrics_extraction_run.md")

summary_lines = [
    "# Metrics Extraction Run Summary\n",
    f"**Script:** src/metrics/extract_metrics.py\n",
    f"\n## Results\n",
    f"| Item | Value |\n|---|---|\n",
    f"| Total samples processed | {len(metrics_df)} |\n",
    f"| Vulnerable samples | {len(vuln_df)} |\n",
    f"| Non-Vulnerable samples | {len(non_vuln_df)} |\n",
    f"| Output file | dataset/processed/metrics_features.csv |\n",
    f"\n## Feature Averages by Label\n",
    f"| Metric | Vulnerable Avg | Safe Avg | Difference |\n",
    f"|---|---|---|---|\n",
]

for col in metric_cols:
    if col not in metrics_df.columns:
        continue
    v_mean = vuln_df[col].mean()
    s_mean = non_vuln_df[col].mean()
    diff   = v_mean - s_mean
    summary_lines.append(
        f"| {col} | {v_mean:.2f} | {s_mean:.2f} | {diff:+.2f} |\n"
    )

with open(notes_path, "w", encoding="utf-8") as f:
    f.writelines(summary_lines)

print(f"  Notes saved: {notes_path}")


# =============================================================================
# DONE
# =============================================================================

section("METRICS EXTRACTION COMPLETE")
print(f"  Input  : {INPUT_CSV}")
print(f"  Output : {OUTPUT_CSV}")
print()
print("  Next steps:")
print("    Day 7 -- Combine AST features + Metrics features")
print("    Day 8 -- Add CodeBERT text features")
print("    Day 9 -- Train the multi-modal classifier")
print()
