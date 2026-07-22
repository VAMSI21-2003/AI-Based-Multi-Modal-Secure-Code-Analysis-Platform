# =============================================================================
# code_intelligence.py -- "AI Code Explanation" static-analysis engine.
#
# This is a DETERMINISTIC, rule-based/statistical analysis engine built on
# the same tree-sitter C grammar already used by app/utils.py for AST
# feature extraction. It does NOT call an external LLM (no API key is
# configured in this environment) and does NOT touch the trained
# classifier -- it is a second, independent derived-artifact layer, in the
# same spirit as ml_bridge.line_risk_scan() / get_ast_tree().
#
# Every function here is computed fresh from the scan's source code on
# every request (see routers/intelligence.py), so results are always in
# sync with whatever was last scanned.
# =============================================================================

import math
import re
from collections import defaultdict, Counter

try:
    import tree_sitter_c as tsc
    from tree_sitter import Language, Parser
    _C_LANGUAGE = Language(tsc.language())
except Exception:
    _C_LANGUAGE = None


# ── Node-type vocabulary (tree-sitter-c grammar) ─────────────────────────────

LOOP_TYPES = {"for_statement", "while_statement", "do_statement"}
DECISION_TYPES = {"if_statement", "case_statement", "conditional_expression"}
CONTROL_KEYWORDS = {"if", "else", "for", "while", "do", "switch", "case", "return", "break", "continue", "goto", "sizeof"}
OPERATOR_PUNCT = {
    "+", "-", "*", "/", "%", "=", "==", "!=", "<", ">", "<=", ">=", "&&", "||", "!",
    "&", "|", "^", "~", "<<", ">>", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
    "<<=", ">>=", "++", "--", "->", ".", "?", ":",
}
OPERAND_TYPES = {"identifier", "field_identifier", "number_literal", "string_literal", "char_literal", "true", "false", "null"}

DANGEROUS_APIS = {
    "strcpy": (4, "CWE-120", "No bounds checking on destination buffer"),
    "strcat": (4, "CWE-120", "No bounds checking on destination buffer"),
    "gets": (4, "CWE-242", "Cannot bound input length -- always unsafe"),
    "sprintf": (3, "CWE-120", "Can overflow destination buffer"),
    "vsprintf": (3, "CWE-120", "Can overflow destination buffer"),
    "scanf": (2, "CWE-120", "%s conversions have no width limit"),
    "alloca": (3, "CWE-770", "Unbounded stack allocation"),
    "system": (3, "CWE-78", "Shell command injection risk"),
    "popen": (3, "CWE-78", "Shell command injection risk"),
    "exec": (2, "CWE-78", "Verify all arguments are sanitised"),
    "memcpy": (2, "CWE-120", "Length should be checked against destination size"),
    "memmove": (2, "CWE-120", "Length should be checked against destination size"),
    "strncpy": (1, "CWE-170", "May not NUL-terminate if source >= size"),
    "malloc": (0, None, None),
    "calloc": (0, None, None),
    "realloc": (1, "CWE-416", "Original pointer must be preserved until success is confirmed"),
    "free": (0, None, None),
    "atoi": (1, "CWE-20", "No error handling for invalid input"),
    "rand": (1, "CWE-338", "Not cryptographically secure"),
}


def _decode(node, source: bytes) -> str:
    try:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    except Exception:
        return ""


def parse(code: str):
    if _C_LANGUAGE is None:
        return None, None
    parser = Parser(_C_LANGUAGE)
    source = bytes(code, "utf-8")
    tree = parser.parse(source)
    return tree.root_node, source


def _walk(node):
    """Depth-first iterator over every node in the tree."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def _find_all(node, types):
    return [n for n in _walk(node) if n.type in types]


def _line(node) -> int:
    return node.start_point[0] + 1


# =============================================================================
# Function discovery
# =============================================================================

def _function_declarator(func_node):
    for child in func_node.children:
        if child.type == "function_declarator":
            return child
        if child.type in ("pointer_declarator",):
            inner = _function_declarator(child)
            if inner:
                return inner
    return None


def _identifier_name(node, source) -> str:
    if node is None:
        return "?"
    if node.type == "identifier":
        return _decode(node, source)
    for child in node.children:
        name = _identifier_name(child, source)
        if name != "?":
            return name
    return "?"


def _function_name(func_node, source) -> str:
    decl = _function_declarator(func_node)
    if decl is None:
        return "anonymous"
    for child in decl.children:
        if child.type in ("identifier",):
            return _decode(child, source)
    return _identifier_name(decl, source)


def _function_params(func_node, source):
    decl = _function_declarator(func_node)
    params = []
    if decl is None:
        return params
    plist = next((c for c in decl.children if c.type == "parameter_list"), None)
    if plist is None:
        return params
    for p in plist.children:
        if p.type != "parameter_declaration":
            continue
        type_node = p.children[0] if p.children else None
        type_text = _decode(type_node, source) if type_node else "?"
        name = _identifier_name(p, source)
        is_pointer = "*" in _decode(p, source)
        params.append({"name": name, "type": type_text, "is_pointer": is_pointer})
    return params


def _return_type(func_node, source) -> str:
    parts = []
    for child in func_node.children:
        if child.type == "function_declarator":
            break
        parts.append(_decode(child, source))
    return " ".join(parts).strip() or "void"


def find_functions(root):
    return _find_all(root, {"function_definition"})


def extract_functions(code: str) -> list:
    """
    Splits `code` into its top-level function definitions using the same
    tree-sitter grammar/parse() + find_functions() this module already uses
    elsewhere (Call Graph Explorer, dependency graph, etc.) -- no new
    parsing logic. Returns a list of {"name", "start_line", "end_line",
    "text"} dicts, one per function, in source order.

    Used by ml_bridge.run_prediction() for per-function live inference
    (docs/PER_FUNCTION_INFERENCE_DESIGN.md) so CodeBERT sees individual
    functions (matching training) instead of a whole file. Returns [] if
    tree-sitter is unavailable or the code contains no function_definition
    nodes (e.g. a header with only declarations) -- callers must treat that
    as a normal "nothing to split" outcome, not an error, and fall back to
    whole-code handling.
    """
    root, source = parse(code)
    if root is None:
        return []
    out = []
    for fn in find_functions(root):
        out.append({
            "name": _function_name(fn, source),
            "start_line": fn.start_point[0] + 1,
            "end_line": fn.end_point[0] + 1,
            "text": _decode(fn, source),
        })
    return out


def find_global_variables(root, source) -> list:
    """
    File-scope (global) variable names -- direct children of the translation
    unit that are plain declarations, not function definitions/prototypes.
    Used to annotate which functions in the Call Graph Explorer share state
    through global variables (a real, if approximate, signal -- a function
    "shares" a global if the name appears as a word in its body text).
    """
    names = []
    for child in root.children:
        if child.type != "declaration":
            continue
        for n in _find_all(child, {"identifier"}):
            name = _decode(n, source)
            if name and name not in names:
                names.append(name)
    return names


# =============================================================================
# Cyclomatic complexity (McCabe): decision points + 1
# =============================================================================

def cyclomatic_complexity(func_node) -> int:
    complexity = 1
    for n in _walk(func_node):
        if n.type in ("if_statement", "for_statement", "while_statement", "do_statement",
                      "case_statement", "conditional_expression"):
            complexity += 1
        elif n.type == "binary_expression":
            op = next((c for c in n.children if c.type in ("&&", "||")), None)
            if op is not None:
                complexity += 1
    return complexity


def max_nesting_depth(func_node) -> int:
    body = next((c for c in func_node.children if c.type == "compound_statement"), func_node)

    def depth(node, current):
        best = current
        is_nesting = node.type in ({"if_statement", "for_statement", "while_statement", "do_statement",
                                     "compound_statement", "switch_statement"})
        nxt = current + 1 if is_nesting else current
        for child in node.children:
            best = max(best, depth(child, nxt))
        return best

    return max(0, depth(body, 0) - 1)


# =============================================================================
# Halstead metrics + Maintainability Index
# =============================================================================

def halstead_metrics(func_node, source):
    operators, operands = [], []
    for n in _walk(func_node):
        if n.child_count > 0:
            continue
        text = _decode(n, source)
        if n.type in OPERAND_TYPES:
            operands.append(text)
        elif text in OPERATOR_PUNCT or n.type in CONTROL_KEYWORDS or (n.type.isalpha() and text in CONTROL_KEYWORDS):
            operators.append(text)
    n1, n2 = len(set(operators)), len(set(operands))
    N1, N2 = len(operators), len(operands)
    vocabulary = max(1, n1 + n2)
    length = N1 + N2
    volume = length * math.log2(vocabulary) if vocabulary > 1 else 0.0
    return {"n1": n1, "n2": n2, "N1": N1, "N2": N2, "volume": round(volume, 2)}


def maintainability_index(volume: float, complexity: int, loc: int) -> float:
    loc = max(1, loc)
    volume = max(1.0, volume)
    raw = 171 - 5.2 * math.log(volume) - 0.23 * complexity - 16.2 * math.log(loc)
    scaled = max(0.0, raw * 100.0 / 171.0)
    return round(min(100.0, scaled), 1)


# =============================================================================
# Memory / pointer / buffer analysis
# =============================================================================

def analyze_memory(root, source):
    calls = _find_all(root, {"call_expression"})
    alloc_calls, free_calls = [], []
    for c in calls:
        fn = c.children[0] if c.children else None
        name = _decode(fn, source) if fn else ""
        if name in ("malloc", "calloc", "realloc"):
            alloc_calls.append({"api": name, "line": _line(c)})
        elif name == "free":
            free_calls.append({"line": _line(c)})

    array_decls = _find_all(root, {"array_declarator"})
    stack_buffers = []
    vlas = []
    for a in array_decls:
        name = _identifier_name(a, source)
        size_node = a.children[-2] if len(a.children) >= 2 else None
        size_text = _decode(size_node, source) if size_node else "?"
        if size_text.isdigit():
            stack_buffers.append({"name": name, "size": int(size_text), "line": _line(a)})
        elif size_text not in ("", "]"):
            vlas.append({"name": name, "expression": size_text, "line": _line(a)})

    balance = len(alloc_calls) - len(free_calls)
    return {
        "allocations": len(alloc_calls),
        "frees": len(free_calls),
        "balance": balance,
        "potential_leak": balance > 0,
        "potential_double_free_risk": balance < 0,
        "alloc_sites": alloc_calls[:20],
        "free_sites": free_calls[:20],
        "stack_buffers": stack_buffers,
        "variable_length_arrays": vlas,
        "stack_bytes_estimate": sum(b["size"] for b in stack_buffers),
    }


def analyze_pointers(root, source):
    pointer_decls = _find_all(root, {"pointer_declarator"})
    derefs = _find_all(root, {"pointer_expression"})
    double_ptr = sum(1 for p in pointer_decls if _decode(p, source).count("*") >= 2)
    null_checks = len(re.findall(r"==\s*NULL|!=\s*NULL|\(\s*!\s*\w+\s*\)", source.decode("utf-8", errors="replace")))
    pointer_vars = len(set(_identifier_name(p, source) for p in pointer_decls))
    coverage = round(min(100.0, (null_checks / pointer_vars) * 100), 1) if pointer_vars else 0.0
    return {
        "pointer_variables": pointer_vars,
        "dereferences": len(derefs),
        "double_pointers": double_ptr,
        "null_checks": null_checks,
        "null_check_coverage_pct": coverage,
    }


def analyze_buffers(root, source, dangerous_hits):
    array_decls = _find_all(root, {"array_declarator"})
    buffers = []
    hit_lines = {h["line"] for h in dangerous_hits}
    for a in array_decls:
        name = _identifier_name(a, source)
        size_node = a.children[-2] if len(a.children) >= 2 else None
        size_text = _decode(size_node, source) if size_node else "?"
        start, end = _line(a), _line(a) + 12
        risky = sorted(l for l in hit_lines if start <= l <= end)
        buffers.append({
            "name": name, "declared_size": size_text if size_text else "unspecified",
            "line": start, "nearby_risk_lines": risky,
        })
    return buffers


def analyze_loops(root, source):
    loops = []

    def enclosing_depth(node):
        depth = 0
        p = node.parent
        while p is not None:
            if p.type in LOOP_TYPES:
                depth += 1
            p = p.parent
        return depth

    for n in _walk(root):
        if n.type not in LOOP_TYPES:
            continue
        body_text = _decode(n, source)
        has_break = bool(re.search(r"\bbreak\b", body_text))
        condition = n.child_by_field_name("condition")
        cond_text = _decode(condition, source)[:60] if condition else ("(no condition)" if n.type == "for_statement" else "")
        looks_infinite = n.type in ("for_statement", "while_statement") and (
            condition is None or cond_text.strip() in ("1", "true")
        )
        loops.append({
            "type": n.type.replace("_statement", ""),
            "line": _line(n),
            "nesting_depth": enclosing_depth(n),
            "condition_preview": cond_text,
            "has_break": has_break,
            "possibly_infinite": bool(looks_infinite and not has_break),
        })
    return loops


def find_dangerous_apis(root, source):
    calls = _find_all(root, {"call_expression"})
    hits = []
    tally = Counter()
    for c in calls:
        fn = c.children[0] if c.children else None
        name = _decode(fn, source) if fn else ""
        if name in DANGEROUS_APIS:
            sev, cwe, desc = DANGEROUS_APIS[name]
            if sev > 0:
                hits.append({"api": name, "line": _line(c), "severity": sev, "cwe": cwe, "description": desc})
            tally[name] += 1
    grouped = []
    seen = set()
    for h in hits:
        if h["api"] in seen:
            continue
        seen.add(h["api"])
        grouped.append({**h, "count": tally[h["api"]]})
    grouped.sort(key=lambda x: -x["severity"])
    return grouped, hits


# =============================================================================
# Call graph (whole file)
# =============================================================================

def build_call_graph(root, source, functions):
    internal_names = {_function_name(f, source) for f in functions}
    nodes = {name: {"id": name, "label": name, "type": "internal"} for name in internal_names}
    edges = []
    seen_edges = set()

    for f in functions:
        caller = _function_name(f, source)
        for c in _find_all(f, {"call_expression"}):
            fn = c.children[0] if c.children else None
            callee = _decode(fn, source) if fn else None
            if not callee:
                continue
            if callee not in nodes:
                nodes[callee] = {"id": callee, "label": callee, "type": "external" if callee not in internal_names else "internal"}
            key = (caller, callee)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({"source": caller, "target": callee})

    return {"nodes": list(nodes.values()), "edges": edges}


# =============================================================================
# Approximate Control Flow Graph (per function)
# =============================================================================

class _CfgBuilder:
    def __init__(self, source):
        self.source = source
        self.nodes = []
        self.edges = []
        self.counter = 0
        self.loop_stack = []  # stack of {"head": loop_head_id, "breaks": [break_node_ids]}

    def _new_node(self, kind, label, line=None):
        self.counter += 1
        nid = f"n{self.counter}"
        self.nodes.append({"id": nid, "kind": kind, "label": label, "line": line})
        return nid

    def _edge(self, a, b, label=None):
        if a is None or b is None:
            return
        self.edges.append({"source": a, "target": b, "label": label})

    def build_function(self, func_node):
        entry = self._new_node("entry", "ENTRY")
        exit_node = self._new_node("exit", "EXIT")
        body = next((c for c in func_node.children if c.type == "compound_statement"), None)
        if body is None:
            self._edge(entry, exit_node)
            return {"nodes": self.nodes, "edges": self.edges}
        head, tails = self._build_block(list(body.children), exit_node)
        self._edge(entry, head or exit_node)
        for t in tails:
            self._edge(t, exit_node)
        return {"nodes": self.nodes, "edges": self.edges}

    def _build_block(self, stmts, func_exit):
        """Build a straight-line sequence of statements, returning (head_id, [open_tail_ids])."""
        stmts = [s for s in stmts if s.type not in ("{", "}", "comment")]
        head = None
        tails = []
        pending_simple = []

        def flush_simple():
            nonlocal head, tails, pending_simple
            if not pending_simple:
                return
            preview = "; ".join(_decode(s, self.source).split("\n")[0][:40] for s in pending_simple[:3])
            if len(pending_simple) > 3:
                preview += f" ... (+{len(pending_simple)-3} more)"
            nid = self._new_node("block", preview or "(empty)", _line(pending_simple[0]))
            if head is None:
                head = nid
            for t in tails:
                self._edge(t, nid)
            tails = [nid]
            pending_simple = []

        for s in stmts:
            if s.type == "if_statement":
                flush_simple()
                cond_node = s.child_by_field_name("condition")
                cond_text = _decode(cond_node, self.source)[:40] if cond_node else ""
                branch = self._new_node("branch", f"if ({cond_text})", _line(s))
                if head is None:
                    head = branch
                for t in tails:
                    self._edge(t, branch)

                consequence = s.child_by_field_name("consequence")
                alt = s.child_by_field_name("alternative")
                then_stmts = list(consequence.children) if consequence and consequence.type == "compound_statement" else ([consequence] if consequence else [])
                then_head, then_tails = self._build_block(then_stmts, func_exit)
                self._edge(branch, then_head, "true") if then_head else None
                new_tails = list(then_tails) if then_head else [branch]

                if alt is not None:
                    # alt is an else_clause node: children are ['else', <statement-or-block>]
                    else_target = next((c for c in alt.children if c.type != "else"), alt)
                    else_stmts = list(else_target.children) if else_target.type == "compound_statement" else [else_target]
                    else_head, else_tails = self._build_block(else_stmts, func_exit)
                    if else_head:
                        self._edge(branch, else_head, "false")
                        new_tails += else_tails
                    else:
                        new_tails.append(branch)
                else:
                    new_tails.append(branch)

                tails = new_tails

            elif s.type in ("for_statement", "while_statement", "do_statement"):
                flush_simple()
                cond_node = s.child_by_field_name("condition")
                cond_text = _decode(cond_node, self.source)[:40] if cond_node else "..."
                loop_head = self._new_node("loop", f"{s.type.split('_')[0]} ({cond_text})", _line(s))
                if head is None:
                    head = loop_head
                for t in tails:
                    self._edge(t, loop_head)

                body = s.child_by_field_name("body")
                body_stmts = list(body.children) if body and body.type == "compound_statement" else ([body] if body else [])
                self.loop_stack.append({"head": loop_head, "breaks": []})
                b_head, b_tails = self._build_block(body_stmts, func_exit)
                loop_ctx = self.loop_stack.pop()
                if b_head:
                    self._edge(loop_head, b_head, "loop")
                    for t in b_tails:
                        self._edge(t, loop_head, "back-edge")
                # The loop is exited either by its condition becoming false
                # (edge from loop_head, added by the caller via `tails`) or
                # by a `break` anywhere in the body (routed here to whatever
                # statement follows the loop).
                tails = [loop_head] + loop_ctx["breaks"]

            elif s.type == "return_statement":
                flush_simple()
                nid = self._new_node("return", _decode(s, self.source)[:40] or "return", _line(s))
                if head is None:
                    head = nid
                for t in tails:
                    self._edge(t, nid)
                self._edge(nid, func_exit)
                tails = []

            elif s.type == "break_statement":
                flush_simple()
                nid = self._new_node("break", "break", _line(s))
                if head is None:
                    head = nid
                for t in tails:
                    self._edge(t, nid)
                if self.loop_stack:
                    self.loop_stack[-1]["breaks"].append(nid)
                tails = []

            elif s.type == "continue_statement":
                flush_simple()
                nid = self._new_node("continue", "continue", _line(s))
                if head is None:
                    head = nid
                for t in tails:
                    self._edge(t, nid)
                if self.loop_stack:
                    self._edge(nid, self.loop_stack[-1]["head"], "continue")
                tails = []

            else:
                pending_simple.append(s)

        flush_simple()
        return head, tails


def build_cfg(func_node, source):
    builder = _CfgBuilder(source)
    return builder.build_function(func_node)


# =============================================================================
# Variable statistics
# =============================================================================

def analyze_variables(func_node, source, params):
    declared = []
    for d in _find_all(func_node, {"declaration"}):
        for child in d.children:
            if child.type in ("identifier",):
                declared.append((_decode(child, source), _decode(d.children[0], source)))
            elif child.type in ("init_declarator", "pointer_declarator", "array_declarator"):
                nm = _identifier_name(child, source)
                declared.append((nm, _decode(d.children[0], source)))

    type_counts = Counter(t.strip() for _, t in declared)
    mutation_counts = Counter()
    for a in _find_all(func_node, {"assignment_expression"}):
        left = a.children[0] if a.children else None
        name = _identifier_name(left, source) if left else None
        if name:
            mutation_counts[name] += 1

    return {
        "total_declared": len(declared),
        "parameters": len(params),
        "locals": len(declared),
        "by_type": dict(type_counts.most_common(10)),
        "most_mutated": [{"name": n, "count": c} for n, c in mutation_counts.most_common(8)],
    }


# =============================================================================
# Advanced static analysis: code smells (additive -- does not affect any
# other section). Each check is independent and best-effort; false
# negatives are preferred over false positives where the two trade off.
# =============================================================================

MAGIC_NUMBER_IGNORE = {"0", "1", "-1", "2"}


def analyze_code_smells(root, source, functions_data) -> dict:
    unused_variables = _find_unused_variables(root, source)
    unreachable_code = _find_unreachable_code(root, source)
    shadow_variables = _find_shadow_variables(root, source)
    magic_numbers = _find_magic_numbers(root, source)
    duplicate_code = _find_duplicate_lines(source)

    long_parameter_lists = [
        {"function": f["name"], "count": len(f["parameters"])}
        for f in functions_data if len(f["parameters"]) > 4
    ]
    large_functions = [
        {"function": f["name"], "loc": f["loc"]}
        for f in functions_data if f["loc"] > 50
    ]
    deep_nesting = [
        {"function": f["name"], "depth": f["max_nesting"]}
        for f in functions_data if f["max_nesting"] >= 5
    ]

    return {
        "unused_variables": unused_variables,
        "unreachable_code": unreachable_code,
        "shadow_variables": shadow_variables,
        "long_parameter_lists": long_parameter_lists,
        "large_functions": large_functions,
        "deep_nesting": deep_nesting,
        "magic_numbers": magic_numbers,
        "duplicate_code": duplicate_code,
        "total_findings": (
            len(unused_variables) + len(unreachable_code) + len(shadow_variables)
            + len(long_parameter_lists) + len(large_functions) + len(deep_nesting)
            + len(magic_numbers) + len(duplicate_code)
        ),
    }


def _find_unused_variables(root, source) -> list:
    findings = []
    for func in find_functions(root):
        declared = {}
        for d in _find_all(func, {"declaration"}):
            for child in d.children:
                name = None
                if child.type in ("identifier", "init_declarator", "pointer_declarator", "array_declarator"):
                    name = _identifier_name(child, source)
                if name and name != "?":
                    declared.setdefault(name, _line(d))

        all_ids = [_decode(n, source) for n in _find_all(func, {"identifier"})]
        id_counts = Counter(all_ids)
        for name, line in declared.items():
            # A declared-and-used variable's identifier appears at least twice
            # (once in the declaration, once+ in usage). Exactly one means unused.
            if id_counts.get(name, 0) <= 1:
                findings.append({"name": name, "line": line})
    return findings[:30]


def _find_unreachable_code(root, source) -> list:
    findings = []
    terminators = {"return_statement", "break_statement", "continue_statement", "goto_statement"}
    for block in _find_all(root, {"compound_statement"}):
        children = [c for c in block.children if c.type not in ("{", "}", "comment")]
        for i, stmt in enumerate(children[:-1]):
            if stmt.type in terminators:
                nxt = children[i + 1]
                findings.append({"line": _line(nxt), "after_line": _line(stmt)})
    return findings[:30]


def _find_shadow_variables(root, source) -> list:
    findings = []
    for func in find_functions(root):
        scopes = []  # stack of sets

        def walk(node, depth=0):
            is_scope = node.type == "compound_statement"
            if is_scope:
                scopes.append({})
            if node.type == "declaration":
                for child in node.children:
                    if child.type in ("identifier", "init_declarator", "pointer_declarator", "array_declarator"):
                        name = _identifier_name(child, source)
                        if name and name != "?":
                            for outer in scopes[:-1] if is_scope else scopes:
                                if name in outer:
                                    findings.append({"name": name, "outer_line": outer[name], "inner_line": _line(node)})
                            if scopes:
                                scopes[-1][name] = _line(node)
            for c in node.children:
                walk(c, depth + 1)
            if is_scope:
                scopes.pop()

        walk(func)
    return findings[:30]


def _find_magic_numbers(root, source) -> list:
    findings = []
    seen_lines = set()
    for n in _find_all(root, {"number_literal"}):
        text = _decode(n, source)
        if text in MAGIC_NUMBER_IGNORE:
            continue
        parent_type = n.parent.type if n.parent else ""
        if parent_type == "array_declarator":  # buffer sizes are not "magic"
            continue
        line = _line(n)
        if line in seen_lines:
            continue
        seen_lines.add(line)
        findings.append({"line": line, "value": text})
    return findings[:30]


def _find_duplicate_lines(source: bytes) -> list:
    text = source.decode("utf-8", errors="replace")
    lines = text.split("\n")
    normalized = {}
    findings = []
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if len(stripped) < 20 or stripped.startswith(("//", "/*", "*")):
            continue
        normalized.setdefault(stripped, []).append(i + 1)
    for snippet, line_nums in normalized.items():
        if len(line_nums) >= 2:
            findings.append({"snippet": snippet[:80], "lines": line_nums})
    return findings[:15]


# =============================================================================
# Function summary (narrative, template-based -- explicitly not an LLM call)
# =============================================================================

def summarize_function(name, params, return_type, cc, loop_count, cond_count,
                        call_names, dangerous, memory, has_recursion) -> str:
    param_desc = ", ".join(f"{p['type']} {p['name']}" for p in params) if params else "no parameters"
    parts = [f"`{name}` returns `{return_type}` and takes {param_desc}."]

    behaviors = []
    if memory["allocations"] > 0:
        behaviors.append(f"performs {memory['allocations']} heap allocation(s)")
    if memory["frees"] > 0:
        behaviors.append(f"releases memory {memory['frees']} time(s)")
    if loop_count > 0:
        behaviors.append(f"iterates using {loop_count} loop(s)")
    if cond_count > 0:
        behaviors.append(f"branches on {cond_count} condition(s)")
    if call_names:
        shown = ", ".join(sorted(set(call_names))[:6])
        behaviors.append(f"calls {shown}")
    if has_recursion:
        behaviors.append("calls itself recursively")
    if behaviors:
        parts.append("It " + "; ".join(behaviors) + ".")

    if cc <= 5:
        parts.append("Control flow is simple (low cyclomatic complexity).")
    elif cc <= 10:
        parts.append("Control flow has moderate complexity.")
    else:
        parts.append(f"Control flow is complex (cyclomatic complexity {cc}) and may be worth refactoring.")

    if dangerous:
        names = ", ".join(sorted({d["api"] for d in dangerous}))
        parts.append(f"⚠ Uses potentially dangerous API(s): {names}.")

    if memory["potential_leak"]:
        parts.append("⚠ Allocation/free count is unbalanced -- review for a possible memory leak.")

    return " ".join(parts)


# =============================================================================
# Composite scores
# =============================================================================

def compute_scores(functions_data, dangerous_hits, vuln_probability, total_loc):
    if not functions_data:
        return {
            "quality": 50, "maintainability_index": 50, "security_score": 50,
            "performance_score": 50, "cyclomatic_complexity_total": 0,
        }

    avg_cc = sum(f["cyclomatic_complexity"] for f in functions_data) / len(functions_data)
    avg_mi = sum(f["maintainability_index"] for f in functions_data) / len(functions_data)
    max_nesting = max((f["max_nesting"] for f in functions_data), default=0)
    long_funcs = sum(1 for f in functions_data if f["loc"] > 50)

    quality = 100
    quality -= min(30, long_funcs * 10)
    quality -= min(30, max(0, avg_cc - 5) * 4)
    quality -= min(20, max(0, max_nesting - 3) * 5)
    quality = max(0, min(100, round(quality)))

    sev_penalty = sum({4: 25, 3: 15, 2: 8, 1: 3}.get(h["severity"], 0) for h in dangerous_hits)
    security_score = max(0, min(100, round(100 - sev_penalty - vuln_probability * 0.4)))

    total_loops = sum(f.get("loop_count", 0) for f in functions_data)
    perf_penalty = min(40, max_nesting * 8) + min(30, max(0, total_loops - 3) * 5) + min(20, max(0, avg_cc - 8) * 3)
    performance_score = max(0, min(100, round(100 - perf_penalty)))

    return {
        "quality": quality,
        "maintainability_index": round(avg_mi, 1),
        "security_score": security_score,
        "performance_score": performance_score,
        "cyclomatic_complexity_total": round(sum(f["cyclomatic_complexity"] for f in functions_data)),
        "cyclomatic_complexity_avg": round(avg_cc, 1),
    }


# =============================================================================
# TOP-LEVEL ENTRY POINT
# =============================================================================

def analyze(code: str, vuln_probability: float = 0.0, cfg_function: str = None) -> dict:
    root, source = parse(code)
    if root is None:
        return {"available": False, "error": "tree-sitter parser unavailable"}

    functions = find_functions(root)
    global_vars = find_global_variables(root, source)
    dangerous_grouped, dangerous_hits = find_dangerous_apis(root, source)
    memory = analyze_memory(root, source)
    pointers = analyze_pointers(root, source)
    buffers = analyze_buffers(root, source, dangerous_hits)
    loops = analyze_loops(root, source)
    call_graph = build_call_graph(root, source, functions)
    internal_names = {n["id"] for n in call_graph["nodes"] if n["type"] == "internal"}

    functions_data = []
    total_loc = len(code.split("\n"))

    for f in functions:
        name = _function_name(f, source)
        params = _function_params(f, source)
        ret = _return_type(f, source)
        cc = cyclomatic_complexity(f)
        nesting = max_nesting_depth(f)
        hal = halstead_metrics(f, source)
        loc = f.end_point[0] - f.start_point[0] + 1
        mi = maintainability_index(hal["volume"], cc, loc)
        f_loops = [l for l in loops if _line(f) <= l["line"] <= _line(f) + loc]
        f_conditions = len(_find_all(f, DECISION_TYPES))
        f_calls = [_decode(c.children[0], source) for c in _find_all(f, {"call_expression"}) if c.children]
        f_dangerous = [h for h in dangerous_hits if _line(f) <= h["line"] <= _line(f) + loc]
        f_memory = {
            "allocations": sum(1 for a in memory["alloc_sites"] if _line(f) <= a["line"] <= _line(f) + loc),
            "frees": sum(1 for a in memory["free_sites"] if _line(f) <= a["line"] <= _line(f) + loc),
        }
        f_memory["balance"] = f_memory["allocations"] - f_memory["frees"]
        f_memory["potential_leak"] = f_memory["balance"] > 0
        has_recursion = name in f_calls
        f_pointer_ops = len(_find_all(f, {"pointer_declarator", "pointer_expression"}))
        f_text = _decode(f, source)
        f_global_refs = [g for g in global_vars if re.search(rf"\b{re.escape(g)}\b", f_text)]

        summary = summarize_function(
            name, params, ret, cc, len(f_loops), f_conditions, f_calls, f_dangerous, f_memory, has_recursion,
        )

        functions_data.append({
            "name": name,
            "return_type": ret,
            "parameters": params,
            "start_line": _line(f),
            "loc": loc,
            "cyclomatic_complexity": cc,
            "max_nesting": nesting,
            "maintainability_index": mi,
            "halstead_volume": hal["volume"],
            "loop_count": len(f_loops),
            "condition_count": f_conditions,
            "pointer_ops": f_pointer_ops,
            "call_count": len(f_calls),
            "calls": sorted(set(f_calls)),
            "is_recursive": has_recursion,
            "dangerous_apis": sorted({h["api"] for h in f_dangerous}),
            "global_refs": sorted(f_global_refs),
            "summary": summary,
        })

    variables = analyze_variables(root, source, functions_data[0]["parameters"] if functions_data else [])

    target_fn = None
    if functions:
        if cfg_function:
            target_fn = next((f for f in functions if _function_name(f, source) == cfg_function), functions[0])
        else:
            target_fn = functions[0]
    cfg = build_cfg(target_fn, source) if target_fn is not None else {"nodes": [], "edges": []}
    cfg_target_name = _function_name(target_fn, source) if target_fn is not None else None

    file_summary = (
        f"This file defines {len(functions)} function(s) totalling {total_loc} lines. "
        + (f"It makes {memory['allocations']} allocation call(s) and {memory['frees']} free call(s). "
           if memory["allocations"] or memory["frees"] else "")
        + (f"{len(dangerous_grouped)} distinct potentially dangerous API(s) were detected. "
           if dangerous_grouped else "No dangerous API patterns were detected. ")
        + (f"Deepest nesting reaches {max((f['max_nesting'] for f in functions_data), default=0)} level(s)."
           if functions_data else "")
    )

    scores = compute_scores(functions_data, dangerous_hits, vuln_probability, total_loc)

    # Dead code: functions defined in this file that are never called by any
    # OTHER function in the file (entry points like main() are exempted).
    all_called = set()
    for f in functions_data:
        all_called.update(c for c in f["calls"] if c != f["name"])
    dead_code = sorted(
        f["name"] for f in functions_data
        if f["name"] not in all_called and f["name"] not in ("main",)
    )

    # Critical nodes: functions that are either dangerous-API callers or
    # unusually complex -- worth highlighting in the call graph.
    critical_nodes = sorted({
        f["name"] for f in functions_data
        if f["dangerous_apis"] or f["cyclomatic_complexity"] >= 8
    })

    code_smells = analyze_code_smells(root, source, functions_data)

    return {
        "available": True,
        "file_summary": file_summary,
        "functions": functions_data,
        "function_count": len(functions_data),
        "global_variables": global_vars,
        "dangerous_apis": dangerous_grouped,
        "memory": memory,
        "pointers": pointers,
        "buffers": buffers,
        "loops": loops,
        "call_graph": call_graph,
        "cfg": {"function": cfg_target_name, "available_functions": [f["name"] for f in functions_data], **cfg},
        "variables": variables,
        "scores": scores,
        "dead_code": dead_code,
        "critical_nodes": critical_nodes,
        "code_smells": code_smells,
    }
