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
# Purely additive: new file, does not modify recommendations.py or the
# existing suggest_secure_rewrite() used by the Recommendations page.
# =============================================================================

import re

MALLOC_FAMILY = re.compile(r"\b(\w+)\s*=\s*(?:\([^)]*\*\s*\)\s*)?(malloc|calloc|realloc)\s*\(")
NULLCHECK_NEARBY = re.compile(r"==\s*NULL|!=\s*NULL|if\s*\(\s*!\s*\w+\s*\)")
FREE_CALL = re.compile(r"\bfree\s*\(\s*(\w+)\s*\)")
MALLOC_MULTIPLY = re.compile(r"(\w+)\s*=\s*(?:\([^)]*\*\s*\)\s*)?malloc\s*\(\s*([\w]+)\s*\*\s*([\w]+)")
SCANF_S = re.compile(r"\bscanf\s*\(\s*\"[^\"]*%s")

STRCPY = re.compile(r"\bstrcpy\s*\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)")
GETS = re.compile(r"\bgets\s*\(\s*([^)]+?)\s*\)")
SPRINTF = re.compile(r"\bsprintf\s*\(\s*([^,]+?)\s*,")


def _card(id_, category, cwe, title, line, original, fixed, explanation, why_safer, detected):
    return {
        "id": id_, "category": category, "cwe": cwe, "title": title, "line": line,
        "original_code": original, "fixed_code": fixed,
        "explanation": explanation, "why_safer": why_safer, "detected": detected,
    }


def _scan_line_patterns(lines):
    cards = []
    n = 0
    for i, line in enumerate(lines):
        m = STRCPY.search(line)
        if m:
            n += 1
            fixed = STRCPY.sub(lambda mm: f"strncpy({mm.group(1)}, {mm.group(2)}, sizeof({mm.group(1)}) - 1); {mm.group(1)}[sizeof({mm.group(1)}) - 1] = '\\0'", line)
            cards.append(_card(f"strcpy-{n}", "strcpy", "CWE-120", "Unbounded strcpy()", i + 1, line.strip(), fixed.strip(),
                                "strcpy() copies until it hits a NUL byte with no regard for the destination buffer's size.",
                                "strncpy() caps the copy at the destination size, and the explicit NUL write guarantees termination even if the source was truncated.",
                                True))
        m = GETS.search(line)
        if m:
            n += 1
            fixed = GETS.sub(lambda mm: f"fgets({mm.group(1)}, sizeof({mm.group(1)}), stdin)", line)
            cards.append(_card(f"gets-{n}", "gets", "CWE-242", "Unsafe gets()", i + 1, line.strip(), fixed.strip(),
                                "gets() cannot be told how large the destination buffer is -- any input longer than the buffer overflows it.",
                                "fgets() takes an explicit size argument, so it can never write past the end of the buffer.",
                                True))
        m = SPRINTF.search(line)
        if m:
            n += 1
            fixed = SPRINTF.sub(lambda mm: f"snprintf({mm.group(1)}, sizeof({mm.group(1)}),", line)
            cards.append(_card(f"sprintf-{n}", "sprintf", "CWE-120", "Unbounded sprintf()", i + 1, line.strip(), fixed.strip(),
                                "sprintf() has no length limit -- a long enough formatted result overflows the destination buffer.",
                                "snprintf() truncates safely at the given size instead of writing past the buffer.",
                                True))
        if SCANF_S.search(line):
            n += 1
            cards.append(_card(f"scanf-{n}", "scanf", "CWE-120", "Unbounded scanf(\"%s\")", i + 1, line.strip(),
                                'char buf[64];\nscanf("%63s", buf);  // width limit = buffer size - 1',
                                "%s in scanf() has no width limit by default, so it can write past the end of the destination buffer.",
                                "A numeric width (e.g. %63s for a 64-byte buffer) bounds how many characters scanf() will write.",
                                True))

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
                                    True))

        mm = MALLOC_MULTIPLY.search(line)
        if mm:
            var, a, b = mm.group(1), mm.group(2), mm.group(3)
            n += 1
            guard = f"if ({a} <= 0 || {b} <= 0 || (size_t){a} > SIZE_MAX / (size_t){b}) return NULL;\n"
            cards.append(_card(f"intoverflow-{n}", "integer_overflow", "CWE-190", "Multiplication inside malloc()", i + 1, line.strip(),
                                guard + line.strip(),
                                f"'{a} * {b}' can wrap around to a small (or zero) value on overflow, causing malloc() to under-allocate.",
                                "Checking the multiplicands against SIZE_MAX before multiplying detects the overflow before it happens, instead of after the undersized buffer is already in use.",
                                True))

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
                                    True))
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
    detected = _scan_line_patterns(lines)
    detected_categories = {c["category"] for c in detected}
    reference = [c for c in REFERENCE_CARDS if c["category"] not in detected_categories]
    return {
        "detected": detected,
        "reference": reference,
        "detected_count": len(detected),
    }
