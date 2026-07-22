# =============================================================================
# rewrite_rules.py -- single source of truth for the pattern-based auto-fix
# rules shared by auto_patch.py (per-line "detected" cards on the dedicated
# AutoPatch page) and recommendations.py (the whole-code
# suggest_secure_rewrite() embedded in every scan response, also used by
# CodeDiff.tsx's "Load current scan's auto-fix").
#
# Before this module existed, each file declared its own copy of the
# strcpy/gets/sprintf regexes and replacement text -- identical in the
# common case, but two independently-edited copies that could silently
# drift apart, and recommendations.py additionally covered strcat while
# auto_patch.py did not (a real, visible inconsistency: CodeDiff/
# Recommendations could show a strcat fix for code where the dedicated
# AutoPatch page would show nothing). This is the one place these four
# rules are defined now; both consumers import from here.
#
# Each rule's safe_replacer/unsafe_replacer take a `re.Match` and return the
# replacement text for `pattern.sub()` -- unsafe_replacer is used instead of
# a fabricated sizeof(dest) whenever patch_safety.destination_capacity_is_known()
# determines the destination's capacity is NOT statically knowable from the
# code being rewritten (see patch_safety.py for why this distinction exists
# and matters -- a "safer" patch built on a fabricated size is not safe).
#
# Not every remediation this platform generates fits this shape (scanf's fix
# computes a numeric field width rather than substituting a snippet; the
# free/malloc-multiply/malloc-nullcheck detectors in auto_patch.py are
# presence/absence heuristics with a fixed insertion, not a pattern
# substitution) -- those remain their own dedicated logic in auto_patch.py,
# not shoehorned into this shared list.
# =============================================================================

import re
from dataclasses import dataclass
from typing import Callable, Pattern


@dataclass(frozen=True)
class RewriteRule:
    id: str                        # e.g. "strcpy" -- card category / changelog key
    cwe: str
    title: str                     # auto_patch.py card title, e.g. "Unbounded strcpy()"
    dest_group: int                # which regex group is the destination variable
    pattern: Pattern
    safe_replacer: Callable        # Match -> str, used when dest capacity is known
    unsafe_replacer: Callable      # Match -> str, used when it is not (dest_size placeholder)
    description: str               # recommendations.py's change-log line
    explanation: str               # auto_patch.py card "what's wrong"
    why_safer_known: str           # auto_patch.py card "why it's safer" (known-capacity case)


REWRITE_RULES = [
    RewriteRule(
        id="strcpy", cwe="CWE-120", title="Unbounded strcpy()", dest_group=1,
        pattern=re.compile(r"\bstrcpy\s*\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)"),
        safe_replacer=lambda m: f"strncpy({m.group(1)}, {m.group(2)}, sizeof({m.group(1)}) - 1); {m.group(1)}[sizeof({m.group(1)}) - 1] = '\\0'",
        unsafe_replacer=lambda m: f"strncpy({m.group(1)}, {m.group(2)}, dest_size - 1); {m.group(1)}[dest_size - 1] = '\\0';  /* TODO: set dest_size to {m.group(1)}'s real capacity */",
        description="Replaced strcpy() with a bounds-checked strncpy() + explicit NUL termination.",
        explanation="strcpy() copies until it hits a NUL byte with no regard for the destination buffer's size.",
        why_safer_known="strncpy() caps the copy at the destination size, and the explicit NUL write guarantees termination even if the source was truncated.",
    ),
    RewriteRule(
        id="strcat", cwe="CWE-120", title="Unbounded strcat()", dest_group=1,
        pattern=re.compile(r"\bstrcat\s*\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)"),
        safe_replacer=lambda m: f"strncat({m.group(1)}, {m.group(2)}, sizeof({m.group(1)}) - strlen({m.group(1)}) - 1)",
        unsafe_replacer=lambda m: f"strncat({m.group(1)}, {m.group(2)}, dest_size - strlen({m.group(1)}) - 1)  /* TODO: set dest_size to {m.group(1)}'s real capacity */",
        description="Replaced strcat() with a bounds-checked strncat().",
        explanation="strcat() appends until it hits a NUL byte with no regard for how much space is actually left in the destination buffer.",
        why_safer_known="strncat() caps the appended length so the destination can never be written past its real size.",
    ),
    RewriteRule(
        id="gets", cwe="CWE-242", title="Unsafe gets()", dest_group=1,
        pattern=re.compile(r"\bgets\s*\(\s*([^)]+?)\s*\)"),
        safe_replacer=lambda m: f"fgets({m.group(1)}, sizeof({m.group(1)}), stdin)",
        unsafe_replacer=lambda m: f"fgets({m.group(1)}, dest_size, stdin)  /* TODO: set dest_size to {m.group(1)}'s real capacity */",
        description="Replaced gets() with fgets() (bounded read).",
        explanation="gets() cannot be told how large the destination buffer is -- any input longer than the buffer overflows it.",
        why_safer_known="fgets() takes an explicit size argument, so it can never write past the end of the buffer.",
    ),
    RewriteRule(
        id="sprintf", cwe="CWE-120", title="Unbounded sprintf()", dest_group=1,
        pattern=re.compile(r"\bsprintf\s*\(\s*([^,]+?)\s*,"),
        safe_replacer=lambda m: f"snprintf({m.group(1)}, sizeof({m.group(1)}),",
        unsafe_replacer=lambda m: f"snprintf({m.group(1)}, dest_size,  /* TODO: set dest_size to {m.group(1)}'s real capacity */",
        description="Replaced sprintf() with snprintf() (bounded formatting).",
        explanation="sprintf() has no length limit -- a long enough formatted result overflows the destination buffer.",
        why_safer_known="snprintf() truncates safely at the given size instead of writing past the buffer.",
    ),
]
