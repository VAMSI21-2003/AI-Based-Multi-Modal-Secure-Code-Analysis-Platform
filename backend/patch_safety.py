# =============================================================================
# patch_safety.py -- shared destination-capacity classification used by both
# remediation engines (auto_patch.py and recommendations.py::suggest_secure_rewrite).
#
# WHY THIS EXISTS: both engines previously emitted `sizeof(dest)` as the
# "safe" bound for strcpy/strcat/gets/sprintf fixes, unconditionally. That is
# only correct when `dest` is a real stack array with a statically visible
# declaration -- if `dest` is actually a function PARAMETER (`char *dest` or
# `char dest[]`, which decays to a pointer), `sizeof(dest)` silently returns
# the pointer's size (4 or 8 bytes on real platforms), not the buffer's real
# capacity. A "safer" patch built on that assumption can be silently wrong.
#
# This module classifies, from the visible source text, whether a variable's
# capacity is genuinely knowable via sizeof(). It is deliberately
# conservative: ANY ambiguity (struct member, array-of-pointers element,
# variable declared outside the visible snippet, etc.) resolves to "not
# known" -- a regex-based engine cannot safely claim certainty it doesn't
# have, and the caller must never fabricate a bound in that case.
# =============================================================================

import re

_ARRAY_DECL_RE = r"\b(?:char|unsigned\s+char|int8_t|uint8_t|wchar_t)\s+{name}\s*\[\s*[A-Za-z0-9_]+\s*\]"
_ARRAY_DECL_NUMERIC_RE = r"\b(?:char|unsigned\s+char|int8_t|uint8_t|wchar_t)\s+{name}\s*\[\s*(\d+)\s*\]"
_POINTER_PARAM_RE = r"\(\s*[^()]*\b(?:char|unsigned\s+char|int8_t|uint8_t|wchar_t)\s*\*\s*{name}\b"
_ARRAY_PARAM_DECAY_RE = r"\(\s*[^()]*\b(?:char|unsigned\s+char|int8_t|uint8_t|wchar_t)\s+{name}\s*\[\s*\]"


def _is_simple_identifier(var_name: str) -> bool:
    """Only plain identifiers can be checked at all -- struct members
    (obj->buf), array elements (arr[i]), and other expressions are always
    treated as unknown, never matched against a declaration."""
    return bool(re.fullmatch(r"[A-Za-z_]\w*", var_name.strip()))


def destination_capacity_is_known(code: str, var_name: str) -> bool:
    """
    True only if `var_name` is a plain identifier with a visible stack-array
    declaration (`char var_name[N]`, N a literal or a named constant --
    sizeof() resolves either correctly at compile time). False for pointer
    parameters, array-parameter decay, struct members, array-index
    expressions, or anything not found at all in the visible source.
    """
    name = var_name.strip()
    if not _is_simple_identifier(name):
        return False
    escaped = re.escape(name)
    if re.search(_POINTER_PARAM_RE.format(name=escaped), code):
        return False
    if re.search(_ARRAY_PARAM_DECAY_RE.format(name=escaped), code):
        return False
    return bool(re.search(_ARRAY_DECL_RE.format(name=escaped), code))


def get_declared_array_size(code: str, var_name: str) -> int | None:
    """
    Returns the buffer's capacity as a real integer ONLY if it's a plain
    identifier declared as `char var_name[<integer literal>]`. Named
    constants (`char var_name[BUFSIZE]`) are NOT resolved to a number here --
    scanf's field width must be a literal in the format string, so a named
    constant genuinely cannot be used to build a safe scanf width fix, and
    this function must not pretend otherwise.
    """
    name = var_name.strip()
    if not _is_simple_identifier(name):
        return None
    if not destination_capacity_is_known(code, name):
        return None
    m = re.search(_ARRAY_DECL_NUMERIC_RE.format(name=re.escape(name)), code)
    return int(m.group(1)) if m else None


UNKNOWN_CAPACITY_NOTE = (
    "This function receives the destination as a pointer, not a stack array with a visible size, "
    "so its real capacity cannot be determined from this code alone. sizeof() on a pointer parameter "
    "would silently return the pointer's size (4 or 8 bytes), not the buffer's actual capacity -- "
    "using it here would be a fabricated, incorrect bound. Add an explicit size parameter to this "
    "function (e.g. `size_t dest_size`) and use it as the bound instead."
)
