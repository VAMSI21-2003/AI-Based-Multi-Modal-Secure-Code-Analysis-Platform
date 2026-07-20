# =============================================================================
# utils.py
# Day 12: Streamlit App -- Utility Functions
# Project: Multi-Modal Code Vulnerability Detection Using CodeBERT
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   This file contains all "helper" functions that do the actual work of
#   extracting features from C source code and computing risk levels.
#
#   It is a "pure Python" file -- it does NOT import Streamlit.
#   This separation keeps the logic clean and testable independently.
#
# FUNCTIONS IN THIS FILE:
#   1. validate_code(code)          -- Check if input is usable C code
#   2. extract_ast_features(code)   -- Get 11 AST structural features
#   3. extract_metric_features(code)-- Get 13 software quality metrics
#   4. build_feature_vector(...)    -- Assemble the 792-dim input vector
#   5. get_risk_level(vuln_prob)    -- Convert probability to risk label
#   6. get_verdict(pred, prob)      -- Build the final result dictionary
#   7. describe_features(ast, met)  -- Human-readable feature descriptions
# =============================================================================

import re       # re: "regular expressions" -- a way to search text for patterns
import numpy as np  # numpy: for numerical arrays (our feature vectors)


# ── CONSTANT: Feature column ordering ─────────────────────────────────────────
#
# CRITICAL: These lists must match EXACTLY the column order used when the
# model was trained (see src/fusion/fuse_features.py).
#
# The XGBoost model was trained on columns in this exact order:
#   [11 AST features] + [13 Metric features] + [768 CodeBERT dims]
#
# If you change the order here, the model will receive features in the wrong
# positions and produce completely wrong predictions.

AST_FEATURE_COLS = [
    "n_functions",       # number of nested function definitions
    "n_loops",           # number of for/while/do loops
    "n_if_statements",   # number of if conditions
    "n_assignments",     # number of assignment expressions (x = ...)
    "n_returns",         # number of return statements
    "n_pointer_ops",     # number of pointer operations (* and ->)
    "n_function_calls",  # number of function call sites
    "n_binary_ops",      # number of binary operations (+, -, *, /, &, |)
    "max_depth",         # deepest nesting level in the AST
    "n_total_nodes",     # total number of nodes in the parse tree
    "n_error_nodes",     # number of parse error nodes (malformed code)
]

METRICS_FEATURE_COLS = [
    "loc",               # lines of code (non-blank, non-comment)
    "function_count",    # number of function definitions
    "loop_count",        # number of loops (mirrors AST branch)
    "if_count",          # number of if statements
    "return_count",      # number of return keywords
    "avg_line_length",   # average characters per line
    "max_line_length",   # longest single line in characters
    "comment_count",     # number of comment lines
    "total_lines",       # all lines including blank and comments
    "blank_lines",       # empty lines
    "nesting_depth",     # deepest curly-brace nesting
    "operator_count",    # count of all operator tokens
    "pointer_count",     # count of * and -> tokens
]

# Total: 11 + 13 + 768 = 792 features
N_AST     = len(AST_FEATURE_COLS)    # 11
N_METRICS = len(METRICS_FEATURE_COLS) # 13
N_EMBED   = 768                        # CodeBERT [CLS] token dimensions
N_TOTAL   = N_AST + N_METRICS + N_EMBED  # 792


# ── FUNCTION 1: validate_code ─────────────────────────────────────────────────

def validate_code(code: str):
    """
    Check whether the pasted/uploaded text looks like a C function.

    WHY: We want to give the user clear feedback early rather than crashing
    deep inside the feature extraction pipeline.

    Parameters:
        code (str): The raw text the user provided.

    Returns:
        (is_valid: bool, message: str)
        is_valid -- True if the code looks reasonable to analyse
        message  -- A human-readable explanation (shown in the UI)
    """

    # --- Check 1: Empty input ------------------------------------------------
    if not code or not code.strip():
        # 'not code' is True if code is None or an empty string ""
        # 'not code.strip()' is True if code is only spaces/newlines
        return False, "No code provided. Please paste or upload a C function."

    # --- Check 2: Minimum length ---------------------------------------------
    # A meaningful C function needs at least a signature + braces + body.
    # Anything under 10 characters is likely accidental or garbage.
    if len(code.strip()) < 10:
        return False, "Input is too short to be a valid C function."

    # --- Check 3: Maximum length warning (not blocking) ----------------------
    # CodeBERT truncates at 512 tokens (~2000 characters).
    # Very long functions are analysed but truncated.
    if len(code) > 8000:
        # We still allow it but warn -- the return below returns True
        return True, (
            "WARNING: This function is very long (>8000 chars). "
            "CodeBERT will truncate at 512 tokens. "
            "The prediction may be less accurate for long functions."
        )

    # --- Check 4: Looks like C code ------------------------------------------
    # We look for at least one of: curly brace, semicolon, or C keywords.
    # This is a loose check -- we don't want to reject valid unusual code.
    c_indicators = ["{", "}", ";", "int ", "void ", "char ", "return", "if (", "for ("]
    has_c_pattern = any(indicator in code for indicator in c_indicators)
    if not has_c_pattern:
        return (
            False,
            "Input does not appear to contain C code. "
            "Please paste a C function (should contain '{', '}', ';', etc.)."
        )

    # All checks passed
    return True, "OK"


# ── FUNCTION 2: extract_ast_features ─────────────────────────────────────────

def extract_ast_features(code: str) -> dict:
    """
    Parse the C function using tree-sitter and extract 11 structural features.

    WHAT IS AN AST?
        Abstract Syntax Tree -- a tree-shaped representation of source code
        where each node is a grammar construct (loop, if, pointer, etc.)

    HOW THIS WORKS:
        1. The tree-sitter parser reads the C code and builds an AST
        2. We walk every node in the tree (depth-first traversal)
        3. For each node, we check its type and increment the right counter
        4. We also track the maximum depth reached

    Parameters:
        code (str): A C function as a plain text string.

    Returns:
        dict: {feature_name: integer_count, ...} with 11 keys
              matching AST_FEATURE_COLS exactly.
              Returns zeros for all features if parsing fails.
    """

    # Start with all counters at zero.
    # dict.fromkeys(list, 0) creates {key: 0} for every key in the list.
    counts = dict.fromkeys(AST_FEATURE_COLS, 0)

    try:
        # Import tree-sitter inside the function.
        # This way, if tree-sitter is not installed, only this function
        # fails (returns zeros) instead of crashing the whole app.
        import tree_sitter_c as tsc
        from tree_sitter import Language, Parser

        # Build the C language grammar object.
        # tsc.language() returns the compiled C grammar from tree-sitter-c.
        # Language(...) wraps it so tree-sitter's Parser can use it.
        C_LANGUAGE = Language(tsc.language())

        # Create a parser configured for the C language.
        parser = Parser(C_LANGUAGE)

        # Parse the code. tree-sitter expects bytes, so we encode to UTF-8.
        # .parse() returns a Tree object.
        tree = parser.parse(bytes(code, "utf-8"))

        # tree.root_node is the top-level node of the AST.
        root = tree.root_node

        # Node types that count as loops
        LOOP_TYPES    = {"for_statement", "while_statement", "do_statement"}
        # Node types that count as pointer operations
        POINTER_TYPES = {"pointer_declarator", "pointer_expression"}

        # ── Depth-first traversal using a stack ──────────────────────────────
        #
        # We use an explicit stack (a Python list used as a stack) instead of
        # recursion. Each item on the stack is a (node, depth) pair.
        # We start with the root at depth 0.
        #
        # Why not recursion?
        #   Python has a default recursion limit of 1000. A large C function
        #   can produce an AST thousands of nodes deep, which would hit that
        #   limit and raise a RecursionError.

        stack = [(root, 0)]  # list of (node, current_depth)

        while stack:
            # .pop() removes and returns the LAST item (LIFO = stack behaviour)
            node, depth = stack.pop()

            # Count every node toward n_total_nodes
            counts["n_total_nodes"] += 1

            # Update max_depth if this node is deeper than any seen so far
            if depth > counts["max_depth"]:
                counts["max_depth"] = depth

            # Check the node type and increment the matching counter
            t = node.type   # t is a string like "if_statement", "ERROR", etc.

            if   t == "function_definition":
                counts["n_functions"]     += 1
            elif t in LOOP_TYPES:
                counts["n_loops"]         += 1
            elif t == "if_statement":
                counts["n_if_statements"] += 1
            elif t == "assignment_expression":
                counts["n_assignments"]   += 1
            elif t == "return_statement":
                counts["n_returns"]       += 1
            elif t in POINTER_TYPES:
                counts["n_pointer_ops"]   += 1
            elif t == "call_expression":
                counts["n_function_calls"]+= 1
            elif t == "binary_expression":
                counts["n_binary_ops"]    += 1
            elif t == "ERROR":
                counts["n_error_nodes"]   += 1

            # Push all children onto the stack at depth+1
            # We push in reverse order so that the first child is processed
            # first (matching natural left-to-right traversal order).
            for child in reversed(node.children):
                stack.append((child, depth + 1))

    except ImportError:
        # tree-sitter is not installed -- return zeros
        # The app will still run using zeros for AST features
        pass
    except Exception:
        # Any other parse error (e.g., completely invalid input) -- return zeros
        pass

    return counts


# ── FUNCTION 3: extract_metric_features ──────────────────────────────────────

def extract_metric_features(code: str) -> dict:
    """
    Compute 13 software quality metrics from the raw C source text.

    This does NOT need tree-sitter -- it uses simple text counting and
    regular expressions (regex). Regex is a mini-language for pattern matching.

    Parameters:
        code (str): A C function as a plain text string.

    Returns:
        dict: {metric_name: value, ...} with 13 keys matching
              METRICS_FEATURE_COLS exactly.
    """

    # Split the code into individual lines.
    # '\n'.split('\n') -> ['', ''] so 'a\nb'.split('\n') -> ['a', 'b']
    lines = code.split("\n")
    total_lines = len(lines)

    # ── Count blank lines ─────────────────────────────────────────────────────
    # A blank line has no non-whitespace characters.
    # .strip() removes leading/trailing whitespace; if result is empty -> blank.
    blank_lines = sum(1 for line in lines if line.strip() == "")

    # ── Count comment lines ───────────────────────────────────────────────────
    # We track whether we are inside a /* ... */ block comment.
    comment_count   = 0
    in_block_comment = False   # True when we are inside a /* */ comment

    for line in lines:
        stripped = line.strip()  # remove leading/trailing spaces

        if in_block_comment:
            # We are inside a block comment -- this whole line is a comment
            comment_count += 1
            if "*/" in stripped:
                # The block comment ends on this line
                in_block_comment = False
        elif stripped.startswith("//"):
            # Single-line comment: // ...
            comment_count += 1
        elif "/*" in stripped:
            # Block comment starts on this line
            comment_count += 1
            if "*/" not in stripped[stripped.index("/*") + 2:]:
                # The block comment does NOT end on the same line
                in_block_comment = True
            # If */ is on the same line, in_block_comment stays False

    # ── Lines of code (LOC) ───────────────────────────────────────────────────
    # LOC = non-blank, non-comment lines.
    # This is an approximation; inline comments are not subtracted.
    loc = total_lines - blank_lines - comment_count
    loc = max(0, loc)  # ensure we never return a negative number

    # ── Line length statistics ────────────────────────────────────────────────
    # Only measure non-blank lines to avoid skewing the average.
    non_blank = [line for line in lines if line.strip()]
    if non_blank:
        avg_line_length = sum(len(l) for l in non_blank) / len(non_blank)
        avg_line_length = round(avg_line_length, 2)  # 2 decimal places
    else:
        avg_line_length = 0.0

    max_line_length = max((len(l) for l in lines), default=0)

    # ── Keyword counts using regex ────────────────────────────────────────────
    #
    # re.findall(pattern, text) returns a list of all matches.
    # len(re.findall(...)) counts the number of matches.
    #
    # \b is a "word boundary" -- it matches the position between a word
    # character (\w) and a non-word character. This prevents matching "format"
    # as containing "for".

    function_count = len(re.findall(r"\b\w+\s*\([^;{]*\)\s*\{", code))
    loop_count     = len(re.findall(r"\b(for|while|do)\b", code))
    if_count       = len(re.findall(r"\bif\b", code))
    return_count   = len(re.findall(r"\breturn\b", code))

    # ── Nesting depth (deepest curly-brace level) ─────────────────────────────
    # We scan character by character.
    # { increases depth; } decreases depth.
    max_depth    = 0
    curr_depth   = 0
    for ch in code:
        if ch == "{":
            curr_depth += 1
            if curr_depth > max_depth:
                max_depth = curr_depth
        elif ch == "}":
            curr_depth = max(0, curr_depth - 1)  # never go below 0

    # ── Operator count ────────────────────────────────────────────────────────
    # Count sequences of operator characters.
    # [+\-*/%&|^~<>=!]+ matches one or more consecutive operator characters.
    operator_count = len(re.findall(r"[+\-*/%&|^~<>=!]+", code))

    # ── Pointer count (* and ->) ──────────────────────────────────────────────
    # \* matches a literal asterisk (needs backslash because * is special in regex)
    # -> matches the arrow operator used for pointer member access
    pointer_count  = len(re.findall(r"(\*|->)", code))

    return {
        "loc":             loc,
        "function_count":  function_count,
        "loop_count":      loop_count,
        "if_count":        if_count,
        "return_count":    return_count,
        "avg_line_length": avg_line_length,
        "max_line_length": max_line_length,
        "comment_count":   comment_count,
        "total_lines":     total_lines,
        "blank_lines":     blank_lines,
        "nesting_depth":   max_depth,
        "operator_count":  operator_count,
        "pointer_count":   pointer_count,
    }


# ── FUNCTION 4: build_feature_vector ─────────────────────────────────────────

def build_feature_vector(ast_feats: dict, metric_feats: dict,
                          embedding: np.ndarray) -> np.ndarray:
    """
    Concatenate the three feature branches into a single 792-dimensional
    numpy array that the XGBoost/RandomForest model can use for prediction.

    IMPORTANT -- ORDER MUST MATCH TRAINING:
        [11 AST features] | [13 Metric features] | [768 CodeBERT dims]
         ^                   ^                      ^
         AST_FEATURE_COLS    METRICS_FEATURE_COLS   embed_000...embed_767

    Parameters:
        ast_feats    (dict):       Output of extract_ast_features()
        metric_feats (dict):       Output of extract_metric_features()
        embedding    (np.ndarray): Shape (768,) from CodeBERT [CLS] token

    Returns:
        np.ndarray of shape (792,) with dtype float64
    """

    # Build a list of AST feature values in the exact column order.
    # dict.get(key, default) returns 0 if the key is missing (safe fallback).
    ast_values    = [float(ast_feats.get(col, 0))    for col in AST_FEATURE_COLS]

    # Same for metric features.
    metric_values = [float(metric_feats.get(col, 0)) for col in METRICS_FEATURE_COLS]

    # np.concatenate joins arrays end-to-end.
    # [array1, array2, array3] -> one long array.
    # np.array(list) converts a Python list to a numpy array.
    feature_vector = np.concatenate([
        np.array(ast_values,    dtype=np.float64),   # shape (11,)
        np.array(metric_values, dtype=np.float64),   # shape (13,)
        embedding.astype(np.float64),                # shape (768,)
    ])

    # Replace any NaN (Not a Number) values with 0.
    # NaN can arise if CodeBERT produces NaN for an unusual input.
    # np.nan_to_num() replaces NaN with 0.0 and Inf with large finite numbers.
    feature_vector = np.nan_to_num(feature_vector, nan=0.0)

    return feature_vector   # shape: (792,)


# ── FUNCTION 5: get_risk_level ────────────────────────────────────────────────

def get_risk_level(vuln_probability: float):
    """
    Convert a raw vulnerability probability (0.0 to 1.0) into a human-readable
    risk level label and a display color.

    This function defines our risk thresholds:
        vuln_prob < 0.30  -->  SAFE        (green)
        vuln_prob < 0.50  -->  LOW RISK    (light green / lime)
        vuln_prob < 0.70  -->  MEDIUM RISK (orange)
        vuln_prob < 0.85  -->  HIGH RISK   (deep orange)
        vuln_prob >= 0.85 -->  CRITICAL    (red)

    These thresholds are tuned for a security application where
    false negatives (missed vulnerabilities) are more costly than
    false positives (unnecessary warnings).

    Parameters:
        vuln_probability (float): Probability that the function is vulnerable.
                                  Range: 0.0 (definitely safe) to 1.0 (definitely vuln)

    Returns:
        (level: str, color: str, emoji: str)
        level  -- text label e.g. "HIGH RISK"
        color  -- CSS/hex color string for the UI
        emoji  -- a visual indicator character
    """

    if vuln_probability < 0.30:
        return "SAFE",        "#28a745", "safe"       # green
    elif vuln_probability < 0.50:
        return "LOW RISK",    "#85c125", "low"        # lime
    elif vuln_probability < 0.70:
        return "MEDIUM RISK", "#fd7e14", "medium"     # orange
    elif vuln_probability < 0.85:
        return "HIGH RISK",   "#dc3545", "high"       # red
    else:
        return "CRITICAL",    "#7b0d1e", "critical"   # dark red


# ── FUNCTION 6: get_verdict ───────────────────────────────────────────────────

def get_verdict(prediction: int, vuln_probability: float, model_name: str) -> dict:
    """
    Assemble the final result dictionary shown in the Streamlit UI.

    Parameters:
        prediction      (int):   0 = safe, 1 = vulnerable (model's class output)
        vuln_probability(float): Probability of being vulnerable (0.0 to 1.0)
        model_name      (str):   Name of the model used e.g. "XGBoost"

    Returns:
        dict with keys:
            verdict          -- "VULNERABLE" or "NOT VULNERABLE"
            vuln_probability -- raw float
            safe_probability -- 1 - vuln_probability
            confidence       -- confidence in the PREDICTED class (as %)
            risk_level       -- e.g. "HIGH RISK"
            risk_color       -- CSS color string
            risk_tag         -- short tag for icon logic
            model_used       -- name of the model
    """

    # Determine the label string
    verdict = "VULNERABLE" if prediction == 1 else "NOT VULNERABLE"

    # Confidence in the predicted class:
    # If predicted vulnerable: confidence = probability of being vulnerable
    # If predicted safe:       confidence = probability of being safe
    safe_probability = 1.0 - vuln_probability
    if prediction == 1:
        confidence = vuln_probability
    else:
        confidence = safe_probability

    risk_level, risk_color, risk_tag = get_risk_level(vuln_probability)

    return {
        "verdict":           verdict,
        "vuln_probability":  round(vuln_probability * 100, 2),   # as percentage
        "safe_probability":  round(safe_probability * 100, 2),
        "confidence":        round(confidence * 100, 2),
        "risk_level":        risk_level,
        "risk_color":        risk_color,
        "risk_tag":          risk_tag,
        "model_used":        model_name,
    }


# ── FUNCTION 7: describe_features ────────────────────────────────────────────

def describe_features(ast_feats: dict, metric_feats: dict) -> list:
    """
    Return a list of human-readable strings describing notable features
    of the analysed function. These are shown in the UI as "insights".

    Parameters:
        ast_feats    (dict): Output of extract_ast_features()
        metric_feats (dict): Output of extract_metric_features()

    Returns:
        list of (insight_text, severity) tuples
        severity is "warning", "info", or "ok" -- used to colour the insight
    """

    insights = []

    # --- Pointer operations --------------------------------------------------
    n_ptr = ast_feats.get("n_pointer_ops", 0)
    if n_ptr >= 10:
        insights.append((
            f"Very high pointer operation count ({n_ptr}). "
            "This is the strongest predictor of C vulnerabilities in our model. "
            "Check all dereferences for null/bounds safety.",
            "warning"
        ))
    elif n_ptr >= 5:
        insights.append((
            f"Elevated pointer usage ({n_ptr} operations). "
            "Review pointer dereferences carefully.",
            "info"
        ))
    else:
        insights.append((
            f"Pointer usage is low ({n_ptr} operations). Low memory-safety risk from pointers.",
            "ok"
        ))

    # --- Loops ---------------------------------------------------------------
    n_loops = ast_feats.get("n_loops", 0)
    if n_loops >= 5:
        insights.append((
            f"Many loops ({n_loops}). Loops iterating over buffers without bounds "
            "checking are a common source of buffer overflow vulnerabilities.",
            "warning"
        ))
    elif n_loops >= 2:
        insights.append((f"Moderate loop count ({n_loops}). Verify bounds on loop conditions.", "info"))

    # --- Function length -----------------------------------------------------
    loc = metric_feats.get("loc", 0)
    if loc >= 80:
        insights.append((
            f"Very long function ({loc} lines of code). Long functions are harder to "
            "review and statistically more likely to contain bugs.",
            "warning"
        ))
    elif loc >= 40:
        insights.append((f"Moderately long function ({loc} LOC). Consider refactoring.", "info"))
    else:
        insights.append((f"Function length is manageable ({loc} LOC).", "ok"))

    # --- Nesting depth -------------------------------------------------------
    depth = metric_feats.get("nesting_depth", 0)
    if depth >= 5:
        insights.append((
            f"Deep nesting ({depth} levels). Deeply nested control flow is harder to "
            "reason about and more error-prone.",
            "warning"
        ))
    elif depth >= 3:
        insights.append((f"Moderate nesting depth ({depth}). Consider simplifying.", "info"))

    # --- Error nodes ---------------------------------------------------------
    n_err = ast_feats.get("n_error_nodes", 0)
    if n_err > 0:
        insights.append((
            f"The C parser found {n_err} parse error node(s). "
            "The code may be incomplete or use non-standard syntax. "
            "AST features may be less accurate.",
            "warning"
        ))

    # --- Comment density -----------------------------------------------------
    comments = metric_feats.get("comment_count", 0)
    total    = metric_feats.get("total_lines", 1)
    if total > 5 and comments / total < 0.05:
        insights.append((
            "Very few comments (<5% of lines). Under-documented code is harder "
            "to audit and correlates weakly with higher bug density.",
            "info"
        ))

    return insights
