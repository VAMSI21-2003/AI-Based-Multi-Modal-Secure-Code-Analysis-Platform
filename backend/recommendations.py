# =============================================================================
# recommendations.py -- AI Recommendation Panel logic.
#
# Produces actionable secure-coding guidance from the SAME signals already
# computed by the existing pipeline (AST features, metrics, line-risk scan)
# plus a transparent, rule-based auto-fix engine for the most common unsafe
# call patterns. This is an expert-system layer on top of the model's
# output, not a modification of the model itself.
# =============================================================================

import re

AUTO_FIXES = [
    (
        re.compile(r"\bstrcpy\s*\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)"),
        lambda m: f"strncpy({m.group(1)}, {m.group(2)}, sizeof({m.group(1)}) - 1); {m.group(1)}[sizeof({m.group(1)}) - 1] = '\\0'",
        "Replaced strcpy() with a bounds-checked strncpy() + explicit NUL termination.",
    ),
    (
        re.compile(r"\bstrcat\s*\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)"),
        lambda m: f"strncat({m.group(1)}, {m.group(2)}, sizeof({m.group(1)}) - strlen({m.group(1)}) - 1)",
        "Replaced strcat() with a bounds-checked strncat().",
    ),
    (
        re.compile(r"\bgets\s*\(\s*([^)]+?)\s*\)"),
        lambda m: f"fgets({m.group(1)}, sizeof({m.group(1)}), stdin)",
        "Replaced gets() with fgets() (bounded read).",
    ),
    (
        re.compile(r"\bsprintf\s*\(\s*([^,]+?)\s*,"),
        lambda m: f"snprintf({m.group(1)}, sizeof({m.group(1)}),",
        "Replaced sprintf() with snprintf() (bounded formatting).",
    ),
]

BEST_PRACTICES = {
    "buffer_overflow": {
        "title": "Buffer Overflow Prevention",
        "tips": [
            "Prefer fixed-size, bounds-checked functions (strncpy, snprintf, strncat) over their unbounded equivalents.",
            "Always pass the destination buffer's size alongside the buffer itself.",
            "Validate lengths BEFORE copying, not after.",
            "Compile with -fstack-protector-strong and _FORTIFY_SOURCE=2.",
        ],
    },
    "null_pointer": {
        "title": "Null Pointer Checks",
        "tips": [
            "Check the return value of every malloc/calloc/realloc/fopen call before dereferencing it.",
            "Reset freed pointers to NULL immediately to make use-after-free crashes visible instead of exploitable.",
            "Prefer a single, consistent error-handling pattern (early return or goto cleanup) so checks are never skipped.",
        ],
    },
    "memory_safety": {
        "title": "Memory Safety",
        "tips": [
            "Pair every malloc()/free() so ownership is unambiguous -- consider a single 'owner' function per allocation.",
            "Run AddressSanitizer (-fsanitize=address) in CI to catch UAF, double-free, and overflows automatically.",
            "Avoid alloca() for anything sized from external/untrusted input.",
        ],
    },
    "input_validation": {
        "title": "Input Validation",
        "tips": [
            "Validate size and range of all externally supplied values before using them in arithmetic, especially before malloc().",
            "Reject or clamp integer inputs used in multiplication that feeds an allocation size.",
            "Treat all network/file/CLI input as untrusted until validated.",
        ],
    },
    "injection": {
        "title": "Injection Prevention",
        "tips": [
            "Never build a shell command by concatenating untrusted input; use exec*() with an explicit argv array instead of system().",
            "Never pass untrusted data directly as a printf-family format string.",
        ],
    },
}


def suggest_secure_rewrite(code: str) -> dict:
    """
    Applies the transparent, pattern-based auto-fix rules above.
    Returns the rewritten code plus a change-log. This is a best-effort,
    rule-based rewrite (not a guarantee of correctness) -- always flagged
    as such to the user.
    """
    rewritten = code
    changes = []
    for pattern, replacer, description in AUTO_FIXES:
        if pattern.search(rewritten):
            rewritten, count = pattern.subn(replacer, rewritten)
            if count:
                changes.append({"description": description, "occurrences": count})
    return {"rewritten_code": rewritten, "changes": changes, "changed": len(changes) > 0}


def generate_recommendations(ast_feats: dict, metric_feats: dict, line_risks: list) -> list:
    """
    Produces a prioritised list of best-practice panels relevant to what was
    actually found in this function (not a generic dump of all tips).
    """
    cwes_found = set()
    for lr in line_risks:
        cwes_found.update(lr.get("cwe", []))

    panels = []

    if cwes_found & {"CWE-120", "CWE-242", "CWE-170"}:
        panels.append(BEST_PRACTICES["buffer_overflow"])
    if cwes_found & {"CWE-476"}:
        panels.append(BEST_PRACTICES["null_pointer"])
    if cwes_found & {"CWE-416", "CWE-770"}:
        panels.append(BEST_PRACTICES["memory_safety"])
    if cwes_found & {"CWE-190", "CWE-125"}:
        panels.append(BEST_PRACTICES["input_validation"])
    if cwes_found & {"CWE-78", "CWE-134"}:
        panels.append(BEST_PRACTICES["injection"])

    # Structural signals independent of specific pattern matches
    if ast_feats.get("n_pointer_ops", 0) >= 8:
        panels.append({
            "title": "High Pointer Complexity",
            "tips": [
                "This function has a high number of pointer operations -- consider extracting pointer-heavy "
                "logic into small, independently-testable helper functions.",
                "Add assertions or bounds checks immediately before each pointer dereference in hot paths.",
            ],
        })
    if metric_feats.get("nesting_depth", 0) >= 5:
        panels.append({
            "title": "Deep Nesting",
            "tips": [
                "Deeply nested control flow is a known correlate of missed edge cases -- consider guard clauses "
                "(early return) to flatten the structure.",
            ],
        })

    if not panels:
        panels.append({
            "title": "General Best Practices",
            "tips": [
                "No specific high-risk pattern was detected -- keep following bounds-checked APIs and validating "
                "all external input as a matter of course.",
            ],
        })

    # de-duplicate by title while preserving order
    seen = set()
    unique_panels = []
    for p in panels:
        if p["title"] not in seen:
            seen.add(p["title"])
            unique_panels.append(p)
    return unique_panels
