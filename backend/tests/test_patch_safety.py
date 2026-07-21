# =============================================================================
# test_patch_safety.py -- regression tests for the sizeof(dest) correctness
# fix (P0 item 3) and the scanf fabrication fix (P0 item 2).
#
# Both remediation engines (auto_patch.py and recommendations.py) previously
# emitted `sizeof(dest)` unconditionally for strcpy/strcat/gets/sprintf
# fixes, which is only correct when `dest` is a real stack array -- silently
# wrong (returns the pointer's size, not the buffer's) when `dest` is a
# function parameter. These tests cover all four required destination
# categories: stack array, pointer parameter, dynamically-allocated buffer,
# and genuinely unknown/undeclared.
# =============================================================================

import patch_safety
import auto_patch
import recommendations

# ── Category 1: stack array (capacity genuinely known) ─────────────────────

STACK_ARRAY_CODE = """
void copy_input(const char *src) {
    char dest[64];
    strcpy(dest, src);
}
"""

STACK_ARRAY_NAMED_CONST_CODE = """
#define BUFSIZE 128
void copy_input(const char *src) {
    char dest[BUFSIZE];
    strcpy(dest, src);
}
"""

# ── Category 2: pointer parameter (capacity NOT known -- the core bug) ─────

POINTER_PARAM_CODE = """
void copy_input(char *dest, const char *src) {
    strcpy(dest, src);
}
"""

ARRAY_PARAM_DECAY_CODE = """
void copy_input(char dest[], const char *src) {
    strcpy(dest, src);
}
"""

# ── Category 3: dynamically-allocated buffer (capacity NOT statically known) ─

MALLOC_BUFFER_CODE = """
void copy_input(const char *src, size_t n) {
    char *dest = malloc(n);
    strcpy(dest, src);
}
"""

# ── Category 4: unknown / not declared in the visible snippet ──────────────

UNKNOWN_DEST_CODE = """
void copy_input(const char *src) {
    strcpy(dest, src);
}
"""


def test_stack_array_with_literal_size_is_known():
    assert patch_safety.destination_capacity_is_known(STACK_ARRAY_CODE, "dest") is True
    assert patch_safety.get_declared_array_size(STACK_ARRAY_CODE, "dest") == 64


def test_stack_array_with_named_constant_is_known_but_size_not_resolved():
    # sizeof(dest) works correctly for named-constant-sized arrays (it's a
    # compile-time operator), so this IS "known" for strcpy/sprintf-style
    # fixes -- but get_declared_array_size must NOT invent a number for it,
    # since scanf's field width requires a literal.
    assert patch_safety.destination_capacity_is_known(STACK_ARRAY_NAMED_CONST_CODE, "dest") is True
    assert patch_safety.get_declared_array_size(STACK_ARRAY_NAMED_CONST_CODE, "dest") is None


def test_pointer_parameter_is_not_known():
    assert patch_safety.destination_capacity_is_known(POINTER_PARAM_CODE, "dest") is False
    assert patch_safety.get_declared_array_size(POINTER_PARAM_CODE, "dest") is None


def test_array_parameter_decay_is_not_known():
    assert patch_safety.destination_capacity_is_known(ARRAY_PARAM_DECAY_CODE, "dest") is False


def test_dynamically_allocated_buffer_is_not_known():
    # A malloc'd pointer's real capacity is not statically visible either --
    # correctly falls into "unknown", matching the "never fabricate" rule.
    assert patch_safety.destination_capacity_is_known(MALLOC_BUFFER_CODE, "dest") is False


def test_undeclared_symbol_is_not_known():
    assert patch_safety.destination_capacity_is_known(UNKNOWN_DEST_CODE, "dest") is False


def test_struct_member_expression_is_never_treated_as_known():
    # Not a plain identifier -- must never be matched against a declaration.
    code = "void f(struct S *obj, const char *src) { strcpy(obj->buf, src); }"
    assert patch_safety.destination_capacity_is_known(code, "obj->buf") is False


# ── auto_patch.py integration: real card generation per category ───────────

def test_auto_patch_strcpy_with_known_stack_array_uses_real_sizeof():
    result = auto_patch.generate_patches(STACK_ARRAY_CODE)
    strcpy_cards = [c for c in result["detected"] if c["category"] == "strcpy"]
    assert len(strcpy_cards) == 1
    assert strcpy_cards[0]["size_known"] is True
    assert "sizeof(dest)" in strcpy_cards[0]["fixed_code"]
    assert "dest_size" not in strcpy_cards[0]["fixed_code"]


def test_auto_patch_strcpy_with_pointer_param_does_not_fabricate_sizeof():
    result = auto_patch.generate_patches(POINTER_PARAM_CODE)
    strcpy_cards = [c for c in result["detected"] if c["category"] == "strcpy"]
    assert len(strcpy_cards) == 1
    assert strcpy_cards[0]["size_known"] is False
    # Must NOT claim sizeof(dest) is correct when dest is a pointer parameter.
    assert "sizeof(dest)" not in strcpy_cards[0]["fixed_code"]
    assert "dest_size" in strcpy_cards[0]["fixed_code"]


def test_auto_patch_scanf_with_known_array_generates_real_width():
    code = """
    void read_input(void) {
        char name[32];
        scanf("%s", name);
    }
    """
    result = auto_patch.generate_patches(code)
    scanf_cards = [c for c in result["detected"] if c["category"] == "scanf"]
    assert len(scanf_cards) == 1
    assert scanf_cards[0]["size_known"] is True
    assert "%31s" in scanf_cards[0]["fixed_code"]
    assert "name" in scanf_cards[0]["fixed_code"]


def test_auto_patch_scanf_with_pointer_param_does_not_fabricate_example():
    code = """
    void read_input(char *name) {
        scanf("%s", name);
    }
    """
    result = auto_patch.generate_patches(code)
    scanf_cards = [c for c in result["detected"] if c["category"] == "scanf"]
    assert len(scanf_cards) == 1
    assert scanf_cards[0]["size_known"] is False
    # The old behavior fabricated an unrelated "char buf[64]" example --
    # the real matched variable name must appear instead, never a fake one.
    assert "name" in scanf_cards[0]["fixed_code"]
    assert "char buf[64]" not in scanf_cards[0]["fixed_code"]


def test_auto_patch_scanf_with_complex_destination_is_honestly_flagged():
    code = 'void f(struct S *s) { scanf("%s", s->name); }'
    result = auto_patch.generate_patches(code)
    scanf_cards = [c for c in result["detected"] if c["category"] == "scanf"]
    assert len(scanf_cards) == 1
    assert scanf_cards[0]["size_known"] is False
    assert "No automatic fix available" in scanf_cards[0]["fixed_code"]


# ── recommendations.py integration ──────────────────────────────────────────

def test_suggest_secure_rewrite_known_array_has_no_manual_sizing_flag():
    result = recommendations.suggest_secure_rewrite(STACK_ARRAY_CODE)
    assert result["changed"] is True
    assert result["requires_manual_sizing"] is False
    assert "sizeof(dest)" in result["rewritten_code"]


def test_suggest_secure_rewrite_pointer_param_flags_manual_sizing():
    result = recommendations.suggest_secure_rewrite(POINTER_PARAM_CODE)
    assert result["changed"] is True
    assert result["requires_manual_sizing"] is True
    assert "dest_size" in result["rewritten_code"]
    assert "sizeof(dest)" not in result["rewritten_code"]
