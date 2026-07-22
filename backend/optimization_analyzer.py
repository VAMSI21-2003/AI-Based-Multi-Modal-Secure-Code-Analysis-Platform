# =============================================================================
# optimization_analyzer.py -- deterministic, tree-sitter-based performance/
# efficiency checks. Same architectural class as code_intelligence.py's
# dangerous-API detector: no ML, no external LLM call, no relation to the
# trained classifier or its risk score. See
# docs/OPTIMIZATION_SUGGESTIONS_DESIGN.md for the design and the honesty
# requirements this module must satisfy.
#
# Every finding in the dict this module returns must be treated as
# "heuristic-based" (see the `heuristic_based` field below) -- never merged
# into vuln_probability/risk_level anywhere downstream.
#
# Re-parses the file independently via code_intelligence.parse()/
# find_functions() (already public, already the shared per-function AST
# entry point per the design's §2) rather than reaching into
# code_intelligence's own private tree-walking helpers, keeping this module
# a separate, self-contained unit -- the "clean module boundary" option the
# design's open question (§4) left for implementation time.
# =============================================================================

import code_intelligence

LOOP_TYPES = {"for_statement", "while_statement", "do_statement"}
STRING_GROWTH_APIS = {"strcat", "strncat", "sprintf", "snprintf"}
HEAP_ALLOC_APIS = {"malloc", "calloc", "realloc"}
LARGE_STRUCT_MEMBER_THRESHOLD = 4  # matches code_intelligence's long_parameter_lists threshold


# ── Local tree-walking helpers (small, self-contained -- see module docstring) ──

def _walk(node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def _find_all(node, types):
    return [n for n in _walk(node) if n.type in types]


def _decode(node, source: bytes) -> str:
    try:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    except Exception:
        return ""


def _line(node) -> int:
    return node.start_point[0] + 1


def _first_identifier(node, source):
    for n in _walk(node):
        if n.type == "identifier":
            return _decode(n, source)
    return None


def _call_args(call_node):
    args = call_node.child_by_field_name("arguments")
    if args is None:
        return []
    return [c for c in args.children if c.type not in ("(", ")", ",")]


def _innermost_enclosing_loop(node):
    p = node.parent
    while p is not None:
        if p.type in LOOP_TYPES:
            return p
        p = p.parent
    return None


def _function_declarator(func_node):
    for child in func_node.children:
        if child.type == "function_declarator":
            return child
        if child.type == "pointer_declarator":
            inner = _function_declarator(child)
            if inner:
                return inner
    return None


def _function_name(func_node, source) -> str:
    decl = _function_declarator(func_node)
    if decl is None:
        return "?"
    ident = next((c for c in decl.children if c.type == "identifier"), None)
    return _decode(ident, source) if ident is not None else "?"


def _function_param_nodes(func_node):
    decl = _function_declarator(func_node)
    if decl is None:
        return []
    plist = next((c for c in decl.children if c.type == "parameter_list"), None)
    if plist is None:
        return []
    return [p for p in plist.children if p.type == "parameter_declaration"]


# =============================================================================
# 1.1 Loop-invariant recomputation in a loop condition
# =============================================================================

def _extract_invariant_length_call(condition, source):
    for call in _find_all(condition, {"call_expression"}):
        fn = call.children[0] if call.children else None
        name = _decode(fn, source) if fn else ""
        if name != "strlen":
            continue
        args = _call_args(call)
        if len(args) == 1 and args[0].type == "identifier":
            return _decode(args[0], source), _decode(call, source)

    for binexp in _find_all(condition, {"binary_expression"}):
        op = next((c for c in binexp.children if c.type == "/"), None)
        if op is None:
            continue
        left, right = binexp.children[0], binexp.children[-1]
        if left.type == "sizeof_expression" and right.type == "sizeof_expression":
            var = _first_identifier(left, source)
            if var:
                return var, _decode(binexp, source)
    return None, None


def _var_touched_in_body(body_node, source, var_name) -> bool:
    for n in _walk(body_node):
        if n.type == "assignment_expression":
            left = n.children[0] if n.children else None
            if left is not None and _first_identifier(left, source) == var_name:
                return True
        elif n.type == "update_expression":
            operand = next((c for c in n.children if c.type not in ("++", "--")), None)
            if operand is not None and _first_identifier(operand, source) == var_name:
                return True
        elif n.type == "pointer_expression":
            if n.children and n.children[0].type == "&":
                operand = n.children[1] if len(n.children) > 1 else None
                if operand is not None and _decode(operand, source).strip() == var_name:
                    return True  # address taken -- possibly mutated elsewhere via pointer
    return False


def _find_loop_invariant_length_calls(root, source):
    findings = []
    for loop in _find_all(root, LOOP_TYPES):
        condition = loop.child_by_field_name("condition")
        body = loop.child_by_field_name("body")
        if condition is None or body is None:
            continue
        var, expr = _extract_invariant_length_call(condition, source)
        if var is None or _var_touched_in_body(body, source, var):
            continue
        findings.append({
            "line": _line(loop),
            "loop_type": loop.type.replace("_statement", ""),
            "variable": var,
            "expression": expr,
            "message": (
                f"'{expr}' is recomputed on every iteration of this loop but "
                f"'{var}' is never modified in the loop body -- hoist it into a "
                "variable declared before the loop."
            ),
        })
    return findings


# =============================================================================
# 1.2 String growth via repeated strcat/sprintf-append inside a loop
# =============================================================================

def _find_string_growth_in_loop(root, source):
    findings = []
    for call in _find_all(root, {"call_expression"}):
        fn = call.children[0] if call.children else None
        name = _decode(fn, source) if fn else ""
        if name not in STRING_GROWTH_APIS:
            continue
        loop = _innermost_enclosing_loop(call)
        if loop is None:
            continue
        args = _call_args(call)
        if not args:
            continue
        dest = args[0]
        if dest.type != "identifier":
            # Pointer/offset arithmetic (e.g. `buf + offset`) is the correct
            # tracked-offset/growable-buffer idiom, not the anti-pattern.
            continue
        dest_text = _decode(dest, source).strip()
        findings.append({
            "line": _line(call),
            "api": name,
            "destination": dest_text,
            "loop_line": _line(loop),
            "message": (
                f"'{name}({dest_text}, ...)' is called every iteration of the loop "
                f"at line {_line(loop)} -- each call re-scans '{dest_text}' for its "
                "end, making this O(n^2) overall. Track an offset/length and write "
                "directly instead."
            ),
        })
    return findings


# =============================================================================
# 1.3 Linear (non-geometric) realloc() growth inside a loop
# =============================================================================

def _classify_realloc_growth(size_node):
    if size_node.type == "identifier":
        return "linear"  # bare loop-counter/increment variable used directly
    if size_node.type == "binary_expression":
        op = next((c for c in size_node.children if c.type in ("+", "-", "*", "<<")), None)
        if op is None:
            return "unknown"
        if op.type in ("+", "-"):
            return "linear"
        return "geometric"  # "*" or "<<" -- doubling/geometric growth
    return "unknown"


def _find_linear_realloc_growth(root, source):
    findings = []
    for call in _find_all(root, {"call_expression"}):
        fn = call.children[0] if call.children else None
        name = _decode(fn, source) if fn else ""
        if name != "realloc":
            continue
        loop = _innermost_enclosing_loop(call)
        if loop is None:
            continue
        args = _call_args(call)
        if len(args) != 2:
            continue
        size_node = args[1]
        if _classify_realloc_growth(size_node) != "linear":
            continue
        size_text = _decode(size_node, source).strip()
        findings.append({
            "line": _line(call),
            "size_expression": size_text,
            "loop_line": _line(loop),
            "message": (
                f"realloc() size grows linearly ('{size_text}') on every iteration "
                f"of the loop at line {_line(loop)} -- each call may copy the whole "
                "buffer, making this O(n^2) amortized. Grow geometrically (e.g. "
                "double the capacity) instead."
            ),
        })
    return findings


# =============================================================================
# 1.4 Heap allocation inside a loop body (review flag, not a definite bug)
# =============================================================================

def _find_heap_alloc_in_loop(root, source):
    grouped = {}  # (start_byte, end_byte) -> {"loop": node, "calls": [...]}
    for call in _find_all(root, {"call_expression"}):
        fn = call.children[0] if call.children else None
        name = _decode(fn, source) if fn else ""
        if name not in HEAP_ALLOC_APIS:
            continue
        loop = _innermost_enclosing_loop(call)
        if loop is None:
            continue
        key = (loop.start_byte, loop.end_byte)
        entry = grouped.setdefault(key, {"loop": loop, "calls": []})
        entry["calls"].append({"api": name, "line": _line(call)})

    findings = []
    for entry in grouped.values():
        loop, calls = entry["loop"], entry["calls"]
        findings.append({
            "loop_line": _line(loop),
            "loop_type": loop.type.replace("_statement", ""),
            "allocation_count": len(calls),
            "allocations": calls,
            "message": (
                f"{len(calls)} heap allocation(s) inside this loop (line {_line(loop)}) "
                "-- confirm this is intentional (each iteration genuinely needs its "
                "own allocation), not hoistable out of the loop."
            ),
        })
    findings.sort(key=lambda f: f["loop_line"])
    return findings


# =============================================================================
# 1.5 Struct passed by value where a pointer would avoid a large copy
# =============================================================================

def _collect_struct_member_counts(root, source):
    counts = {}
    for spec in _find_all(root, {"struct_specifier"}):
        body = next((c for c in spec.children if c.type == "field_declaration_list"), None)
        if body is None:
            continue  # a bare `struct Foo` reference, not a definition
        member_count = sum(1 for c in body.children if c.type == "field_declaration")
        name_node = next((c for c in spec.children if c.type == "type_identifier"), None)
        if name_node is not None:
            counts[_decode(name_node, source)] = member_count
        parent = spec.parent
        if parent is not None and parent.type == "type_definition":
            for c in parent.children:
                if c.type == "type_identifier":
                    counts[_decode(c, source)] = member_count
    return counts


def _find_large_struct_by_value(root, source, functions, threshold=LARGE_STRUCT_MEMBER_THRESHOLD):
    struct_members = _collect_struct_member_counts(root, source)
    findings = []
    for func in functions:
        fname = _function_name(func, source)
        for p in _function_param_nodes(func):
            if any(c.type in ("pointer_declarator", "array_declarator") for c in p.children):
                continue
            type_node = p.children[0] if p.children else None
            if type_node is None:
                continue
            struct_name = None
            if type_node.type == "struct_specifier":
                ident = next((c for c in type_node.children if c.type == "type_identifier"), None)
                if ident is not None:
                    struct_name = _decode(ident, source)
            elif type_node.type == "type_identifier":
                struct_name = _decode(type_node, source)
            if struct_name is None or struct_name not in struct_members:
                continue
            member_count = struct_members[struct_name]
            if member_count <= threshold:
                continue
            param_name_node = next((c for c in reversed(p.children) if c.type == "identifier"), None)
            param_name = _decode(param_name_node, source) if param_name_node is not None else "?"
            findings.append({
                "function": fname,
                "parameter": param_name,
                "struct_name": struct_name,
                "member_count": member_count,
                "line": _line(p),
                "message": (
                    f"'{fname}()' parameter '{param_name}' is a struct '{struct_name}' "
                    f"with {member_count} members passed by value -- likely copies more "
                    "than necessary (member count is a proxy for size, not a measured "
                    "byte cost); consider passing a pointer/const pointer instead."
                ),
            })
    return findings


# =============================================================================
# TOP-LEVEL ENTRY POINT
# =============================================================================

def analyze(code: str) -> dict:
    root, source = code_intelligence.parse(code)
    if root is None:
        return {"available": False, "heuristic_based": True, "error": "tree-sitter parser unavailable"}

    functions = code_intelligence.find_functions(root)

    loop_invariant_length_calls = _find_loop_invariant_length_calls(root, source)
    string_growth_in_loop = _find_string_growth_in_loop(root, source)
    linear_realloc_growth = _find_linear_realloc_growth(root, source)
    heap_alloc_in_loop = _find_heap_alloc_in_loop(root, source)
    large_struct_by_value = _find_large_struct_by_value(root, source, functions)

    total_findings = (
        len(loop_invariant_length_calls) + len(string_growth_in_loop)
        + len(linear_realloc_growth) + len(heap_alloc_in_loop) + len(large_struct_by_value)
    )

    return {
        "available": True,
        "heuristic_based": True,
        "loop_invariant_length_calls": loop_invariant_length_calls,
        "string_growth_in_loop": string_growth_in_loop,
        "linear_realloc_growth": linear_realloc_growth,
        "heap_alloc_in_loop": heap_alloc_in_loop,
        "large_struct_by_value": large_struct_by_value,
        "total_findings": total_findings,
    }
