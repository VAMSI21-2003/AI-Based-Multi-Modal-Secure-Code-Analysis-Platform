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

import patch_safety

# Each entry: (pattern, dest_group_index, safe_replacer, unsafe_replacer, description).
# `safe_replacer`/`unsafe_replacer` both take the match object; `unsafe_replacer`
# is used instead of a fabricated sizeof(dest) whenever patch_safety determines
# the destination's capacity is NOT statically knowable from the code being
# rewritten (see patch_safety.py for why this distinction is required).
AUTO_FIXES = [
    (
        re.compile(r"\bstrcpy\s*\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)"),
        1,
        lambda m: f"strncpy({m.group(1)}, {m.group(2)}, sizeof({m.group(1)}) - 1); {m.group(1)}[sizeof({m.group(1)}) - 1] = '\\0'",
        lambda m: f"strncpy({m.group(1)}, {m.group(2)}, dest_size - 1); {m.group(1)}[dest_size - 1] = '\\0';  /* TODO: set dest_size to {m.group(1)}'s real capacity */",
        "Replaced strcpy() with a bounds-checked strncpy() + explicit NUL termination.",
    ),
    (
        re.compile(r"\bstrcat\s*\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)"),
        1,
        lambda m: f"strncat({m.group(1)}, {m.group(2)}, sizeof({m.group(1)}) - strlen({m.group(1)}) - 1)",
        lambda m: f"strncat({m.group(1)}, {m.group(2)}, dest_size - strlen({m.group(1)}) - 1)  /* TODO: set dest_size to {m.group(1)}'s real capacity */",
        "Replaced strcat() with a bounds-checked strncat().",
    ),
    (
        re.compile(r"\bgets\s*\(\s*([^)]+?)\s*\)"),
        1,
        lambda m: f"fgets({m.group(1)}, sizeof({m.group(1)}), stdin)",
        lambda m: f"fgets({m.group(1)}, dest_size, stdin)  /* TODO: set dest_size to {m.group(1)}'s real capacity */",
        "Replaced gets() with fgets() (bounded read).",
    ),
    (
        re.compile(r"\bsprintf\s*\(\s*([^,]+?)\s*,"),
        1,
        lambda m: f"snprintf({m.group(1)}, sizeof({m.group(1)}),",
        lambda m: f"snprintf({m.group(1)}, dest_size,  /* TODO: set dest_size to {m.group(1)}'s real capacity */",
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

    Each substitution is checked against patch_safety.destination_capacity_is_known()
    on the ORIGINAL code (not the partially-rewritten string) before deciding
    whether to emit a real sizeof(dest)-based bound or an honestly-labeled
    dest_size placeholder -- see patch_safety.py for why this matters.
    """
    original = code
    rewritten = code
    changes = []
    any_unsafe = False
    for pattern, dest_group, safe_replacer, unsafe_replacer, description in AUTO_FIXES:
        matches = list(pattern.finditer(rewritten))
        if not matches:
            continue
        count = 0
        unsafe_count = 0

        def _replace(m):
            nonlocal count, unsafe_count
            count += 1
            dest = m.group(dest_group)
            if patch_safety.destination_capacity_is_known(original, dest):
                return safe_replacer(m)
            unsafe_count += 1
            return unsafe_replacer(m)

        rewritten = pattern.sub(_replace, rewritten)
        if count:
            label = description
            if unsafe_count:
                any_unsafe = True
                label += (
                    f" ({unsafe_count} of {count} occurrence(s) use a dest_size PLACEHOLDER, not a real size -- "
                    "destination capacity could not be determined from this code; see patch_safety notes)"
                )
            changes.append({"description": label, "occurrences": count})
    return {
        "rewritten_code": rewritten, "changes": changes, "changed": len(changes) > 0,
        "requires_manual_sizing": any_unsafe,
    }


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
