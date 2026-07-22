# =============================================================================
# auto_patch.py -- AI Auto Patch Generator.
#
# For each vulnerability class requested, produces a patch card:
#   Original code -> Fixed code -> Explanation -> Why it's safer
#
# Two kinds of cards:
#   - DETECTED cards: derived from the actual scanned source (real line,
#     real proposed edit) via targeted regex/heuristic scanning.
#   - REFERENCE cards: shown for classes where no instance of the pattern
#     is safely auto-fixable from a single line (e.g. memory leaks, generic
#     pointer misuse) -- a canonical vulnerable/secure example instead, so
#     the requested category is still fully documented on the page.
#
# Every DETECTED card also carries `size_known`: whether the proposed fix's
# bound (sizeof(dest), or a literal scanf width) is backed by a real,
# statically-visible declaration in the scanned code, or is a template the
# developer must fill in with the real capacity. See patch_safety.py for why
# this distinction exists and matters -- a "safer" patch built on a
# fabricated size is not actually safe.
#
# Shares its strcpy/strcat/gets/sprintf detection+fix rules with
# recommendations.py's suggest_secure_rewrite() via rewrite_rules.py, rather
# than maintaining a second, independent copy of those regexes (previously
# this file also lacked strcat coverage that recommendations.py had --
# importing the same shared list closes that gap). scanf (computes a
# numeric field width rather than substituting a snippet) and the
# free/malloc-multiply/malloc-nullcheck detectors (presence/absence
# heuristics with a fixed insertion, not a pattern substitution) don't fit
# that shared shape and remain their own dedicated logic below.
# =============================================================================

import re

import patch_safety
from rewrite_rules import REWRITE_RULES

MALLOC_FAMILY = re.compile(r"\b(\w+)\s*=\s*(?:\([^)]*\*\s*\)\s*)?(malloc|calloc|realloc)\s*\(")
NULLCHECK_NEARBY = re.compile(r"==\s*NULL|!=\s*NULL|if\s*\(\s*!\s*\w+\s*\)")
FREE_CALL = re.compile(r"\bfree\s*\(\s*(\w+)\s*\)")
MALLOC_MULTIPLY = re.compile(r"(\w+)\s*=\s*(?:\([^)]*\*\s*\)\s*)?malloc\s*\(\s*([\w]+)\s*\*\s*([\w]+)")

# Matches the common, safely-parseable case: one %s conversion, one plain
# identifier argument. Anything more complex (multiple conversions, a
# non-identifier argument) intentionally falls through to a generic,
# honestly-labeled card rather than guessing.
SCANF_ONE_ARG = re.compile(r'\bscanf\s*\(\s*"([^"]*)"\s*,\s*([A-Za-z_]\w*)\s*\)')
SCANF_ANY = re.compile(r'\bscanf\s*\(\s*"[^"]*%s')


def _card(id_, category, cwe, title, line, original, fixed, explanation, why_safer, detected, size_known=True):
    return {
        "id": id_, "category": category, "cwe": cwe, "title": title, "line": line,
        "original_code": original, "fixed_code": fixed,
        "explanation": explanation, "why_safer": why_safer, "detected": detected,
        "size_known": size_known,
    }


def _scan_line_patterns(code: str, lines):
    cards = []
    n = 0
    for i, line in enumerate(lines):
        for rule in REWRITE_RULES:
            m = rule.pattern.search(line)
            if not m:
                continue
            n += 1
            dest = m.group(rule.dest_group)
            known = patch_safety.destination_capacity_is_known(code, dest)
            replacer = rule.safe_replacer if known else rule.unsafe_replacer
            fixed = rule.pattern.sub(replacer, line).strip()
            why_safer = rule.why_safer_known if known else patch_safety.UNKNOWN_CAPACITY_NOTE
            cards.append(_card(f"{rule.id}-{n}", rule.id, rule.cwe, rule.title, i + 1, line.strip(), fixed,
                                rule.explanation, why_safer, True, size_known=known))

        scanf_one = SCANF_ONE_ARG.search(line)
        if scanf_one:
            fmt, dest = scanf_one.group(1), scanf_one.group(2)
            if "%s" in fmt:
                n += 1
                capacity = patch_safety.get_declared_array_size(code, dest)
                if capacity is not None and fmt.count("%s") == 1:
                    width = capacity - 1
                    fixed_fmt = fmt.replace("%s", f"%{width}s", 1)
                    fixed = f'scanf("{fixed_fmt}", {dest});  // width limit = {dest}\'s real declared size ({capacity}) - 1'
                    cards.append(_card(f"scanf-{n}", "scanf", "CWE-120", 'Unbounded scanf("%s")', i + 1, line.strip(), fixed,
                                        "%s in scanf() has no width limit by default, so it can write past the end of the destination buffer.",
                                        f"A numeric width (%{width}s) bounds how many characters scanf() will write into '{dest}', matching its real declared size.",
                                        True, size_known=True))
                else:
                    reason = ("multiple conversions in one format string" if fmt.count("%s") != 1
                               else f"'{dest}'s declared capacity could not be determined from this code")
                    fixed = f'scanf("{fmt}", {dest});  /* TODO: add an explicit width to %s once you know {dest}\'s real capacity -- {reason} */'
                    cards.append(_card(f"scanf-{n}", "scanf", "CWE-120", 'Unbounded scanf("%s")', i + 1, line.strip(), fixed,
                                        "%s in scanf() has no width limit by default, so it can write past the end of the destination buffer.",
                                        f"Could not derive a safe width automatically ({reason}); this shows the real matched call with the manual step still required -- not a fabricated size.",
                                        True, size_known=False))
        elif SCANF_ANY.search(line):
            # A scanf("...%s...") call exists but its destination argument
            # wasn't a single plain identifier (e.g. a struct member, a
            # computed expression, or multiple arguments) -- do not invent a
            # destination name or a size. Flag it honestly instead.
            n += 1
            cards.append(_card(f"scanf-{n}", "scanf", "CWE-120", 'Unbounded scanf("%s")', i + 1, line.strip(),
                                "/* No automatic fix available: this call's destination could not be parsed from the surrounding code. Manually add an explicit width to %s bounded by the real destination capacity. */",
                                "%s in scanf() has no width limit by default, so it can write past the end of the destination buffer.",
                                "This destination expression is too complex for this deterministic engine to safely rewrite automatically.",
                                True, size_known=False))

        mf = FREE_CALL.search(line)
        if mf:
            var = mf.group(1)
            lookahead = "\n".join(lines[i:i + 3])
            if not re.search(rf"{re.escape(var)}\s*=\s*NULL", lookahead):
                n += 1
                cards.append(_card(f"doublefree-{n}", "double_free", "CWE-416", "Pointer not reset after free()", i + 1, line.strip(),
                                    f"{line.strip()}\n{var} = NULL;",
                                    f"'{var}' is freed but not reset -- any later use (or a second free()) is a use-after-free / double-free.",
                                    "Resetting the pointer to NULL makes a later dereference crash immediately and predictably instead of corrupting memory silently, and a second free(NULL) is a safe no-op.",
                                    True, size_known=True))

        mm = MALLOC_MULTIPLY.search(line)
        if mm:
            var, a, b = mm.group(1), mm.group(2), mm.group(3)
            n += 1
            guard = f"if ({a} <= 0 || {b} <= 0 || (size_t){a} > SIZE_MAX / (size_t){b}) return NULL;\n"
            cards.append(_card(f"intoverflow-{n}", "integer_overflow", "CWE-190", "Multiplication inside malloc()", i + 1, line.strip(),
                                guard + line.strip(),
                                f"'{a} * {b}' can wrap around to a small (or zero) value on overflow, causing malloc() to under-allocate.",
                                "Checking the multiplicands against SIZE_MAX before multiplying detects the overflow before it happens, instead of after the undersized buffer is already in use.",
                                True, size_known=True))

        mmal = MALLOC_FAMILY.search(line)
        if mmal:
            var = mmal.group(1)
            lookahead = "\n".join(lines[i:i + 3])
            if not NULLCHECK_NEARBY.search(lookahead):
                n += 1
                cards.append(_card(f"nullcheck-{n}", "malloc_misuse", "CWE-476", "Allocation result not NULL-checked", i + 1, line.strip(),
                                    f"{line.strip()}\nif ({var} == NULL) {{\n    /* handle allocation failure */\n    return NULL;\n}}",
                                    f"'{var}' is used without first confirming the allocation succeeded -- if it returned NULL, the next use is a NULL dereference.",
                                    "An explicit check turns a random crash deep in the function into a clean, predictable early return at the point of failure.",
                                    True, size_known=True))
    return cards


REFERENCE_CARDS = [
    _card("ref-pointer", "pointer_misuse", "CWE-476", "Pointer Misuse (reference)", None,
          "int *p;\n*p = 5;  // p was never assigned",
          "int *p = NULL;\nif (condition) {\n    p = &value;\n}\nif (p != NULL) {\n    *p = 5;\n}",
          "A pointer was dereferenced without ever being assigned a valid address, or without checking that a conditional assignment actually ran.",
          "Initialising to NULL and checking before dereferencing turns undefined behaviour into a controlled, checkable state.",
          False),
    _card("ref-bufferoverflow", "buffer_overflow", "CWE-120", "Buffer Overflow (reference)", None,
          "char buf[16];\nmemcpy(buf, src, len);  // len not checked against 16",
          "char buf[16];\nif (len > sizeof(buf)) len = sizeof(buf);\nmemcpy(buf, src, len);",
          "memcpy()'s length argument came from an untrusted or unchecked source and can exceed the destination buffer.",
          "Clamping the length to the destination's size guarantees memcpy() can never write past the buffer.",
          False),
    _card("ref-nullderef", "null_dereference", "CWE-476", "NULL Dereference (reference)", None,
          "FILE *f = fopen(path, \"r\");\nfread(buf, 1, n, f);  // f may be NULL",
          "FILE *f = fopen(path, \"r\");\nif (f == NULL) return -1;\nfread(buf, 1, n, f);",
          "Any function that can return NULL on failure (fopen, malloc, a lookup function) is used without checking first.",
          "A guard clause immediately after the call stops execution before the bad pointer can be dereferenced.",
          False),
    _card("ref-leak", "memory_leak", "CWE-401", "Memory Leak (reference)", None,
          "void f(void) {\n    char *buf = malloc(1024);\n    if (error_condition) return;  // buf leaked\n    free(buf);\n}",
          "void f(void) {\n    char *buf = malloc(1024);\n    if (error_condition) { free(buf); return; }\n    free(buf);\n}",
          "An early-return path skips the free() at the end of the function, leaking the allocation every time that path is taken.",
          "Every return path needs its own matching free() (or a single cleanup label reached via goto) so no path can skip it -- C's nearest equivalent to RAII-style automatic cleanup, since C has no destructors.",
          False),
]


def generate_patches(code: str) -> dict:
    lines = code.split("\n")
    detected = _scan_line_patterns(code, lines)
    detected_categories = {c["category"] for c in detected}
    reference = [c for c in REFERENCE_CARDS if c["category"] not in detected_categories]
    return {
        "detected": detected,
        "reference": reference,
        "detected_count": len(detected),
    }
