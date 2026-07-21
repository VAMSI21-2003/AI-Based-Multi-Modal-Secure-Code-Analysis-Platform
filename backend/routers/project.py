# =============================================================================
# routers/project.py -- Project Scanner + Security Risk Map (V2 Features 1+2)
# and the cross-file Dependency Graph (Phase 7). Purely additive, read-only
# aggregation over existing ScanRecord rows for a given batch_id. No schema
# changes, no new tables, no changes to how scans are created (POST
# /api/scan/batch already handles folder/zip upload).
# =============================================================================

import re
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import analysis_cache
import code_intelligence
import knowledge_base
from database import get_db, ScanRecord
from scan_service import record_to_dict
from repo_analysis import folder_scores

_SEVERITY_KEY = {4: "critical", 3: "high", 2: "medium", 1: "low"}

router = APIRouter(prefix="/api/project", tags=["project"])

RISK_ORDER = ["SAFE", "LOW RISK", "MEDIUM RISK", "HIGH RISK", "CRITICAL"]
_INCLUDE_RE = re.compile(r'#\s*include\s*"([^"]+)"')


@router.get("/{batch_id}/summary")
def project_summary(batch_id: str, db: Session = Depends(get_db)):
    records = db.query(ScanRecord).filter(ScanRecord.batch_id == batch_id).order_by(ScanRecord.created_at).all()
    if not records:
        raise HTTPException(status_code=404, detail="Project batch not found")

    files = [record_to_dict(r, include_code=False) for r in records]
    total = len(files)
    vulnerable = [f for f in files if f["verdict"] == "VULNERABLE"]
    safe = [f for f in files if f["verdict"] != "VULNERABLE"]

    highest_risk = max(files, key=lambda f: f["vuln_probability"], default=None)

    risk_distribution = {k: 0 for k in RISK_ORDER}
    for f in files:
        risk_distribution[f["risk_level"]] = risk_distribution.get(f["risk_level"], 0) + 1
    risk_distribution = {k: v for k, v in risk_distribution.items() if v > 0}

    avg_vuln_prob = sum(f["vuln_probability"] for f in files) / total if total else 0.0
    security_score = round(max(0.0, 100.0 - avg_vuln_prob), 1)

    # Repository-wide rollups (Repository Scanner, Phase 3 + Phase 5.2):
    # function count, dangerous APIs, CWEs, maintainability, most dangerous
    # function, and per-severity finding counts across every scanned file --
    # built from the same code_intelligence.analyze() / line_risk_scan output
    # already used by Call Graph / File Explorer / Knowledge Graph / Heatmap,
    # so these are real aggregates, not estimates. Routed through
    # analysis_cache (per-ScanRecord.id, safe since code/vuln_probability are
    # immutable post-creation) instead of recomputing on every request.
    function_count = 0
    api_counter: Counter = Counter()
    cwe_counter: Counter = Counter()
    mi_values = []
    most_dangerous_function = None  # highest dangerous-API count, tie-broken by complexity
    finding_severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for r in records:
        intel = analysis_cache.get_intel(r)
        if intel.get("available"):
            function_count += intel.get("function_count", 0)
            for d in intel.get("dangerous_apis", []):
                api_counter[d["api"]] += d.get("count", 1)
                if d.get("cwe"):
                    cwe_counter[d["cwe"]] += d.get("count", 1)
            for fn in intel.get("functions", []):
                mi_values.append(fn["maintainability_index"])
                n_dangerous = len(fn.get("dangerous_apis", []))
                if n_dangerous == 0:
                    continue
                candidate = {
                    "name": fn["name"], "file": r.filename,
                    "dangerous_api_count": n_dangerous, "complexity": fn["cyclomatic_complexity"],
                }
                if most_dangerous_function is None or (
                    candidate["dangerous_api_count"], candidate["complexity"]
                ) > (most_dangerous_function["dangerous_api_count"], most_dangerous_function["complexity"]):
                    most_dangerous_function = candidate

        for lr in analysis_cache.get_line_risks(r):
            key = _SEVERITY_KEY.get(lr["severity"])
            if key:
                finding_severity_counts[key] += 1

    most_dangerous_apis = [{"api": a, "count": c} for a, c in api_counter.most_common(8)]
    most_common_cwe = [
        {"cwe": cwe, "count": c, "name": knowledge_base.lookup(cwe)["name"]}
        for cwe, c in cwe_counter.most_common(8)
    ]

    folders = folder_scores(files)
    most_dangerous_folder = folders[0] if folders else None

    total_loc = sum(r.loc or 0 for r in records)
    avg_confidence = round(sum(r.confidence for r in records) / total, 1) if total else 0.0
    avg_maintainability = round(sum(mi_values) / len(mi_values), 1) if mi_values else None
    created_ats = [r.created_at for r in records]
    scan_duration_sec = round((max(created_ats) - min(created_ats)).total_seconds(), 1)

    return {
        "batch_id": batch_id,
        "project_name": records[0].project_name,
        "created_at": records[0].created_at.isoformat() + "Z",
        "total_files": total,
        "safe_files": len(safe),
        "vulnerable_files": len(vulnerable),
        "highest_risk_file": highest_risk,
        "security_score": security_score,
        "risk_distribution": risk_distribution,
        "function_count": function_count,
        "most_dangerous_apis": most_dangerous_apis,
        "most_common_cwe": most_common_cwe,
        "total_loc": total_loc,
        "avg_confidence": avg_confidence,
        "avg_maintainability": avg_maintainability,
        "most_dangerous_folder": most_dangerous_folder,
        "most_dangerous_function": most_dangerous_function,
        "finding_severity_counts": finding_severity_counts,
        "scan_duration_sec": scan_duration_sec,
        "files": files,
    }


def _find_cycles(adjacency: dict) -> list:
    """
    Plain DFS-based cycle detection over a directed graph given as an
    adjacency dict {node: [neighbours]}. Returns a list of cycles, each a
    list of node ids in order. Small graphs only (project batches), so no
    need for Tarjan's -- this is O(V+E) per start node, bounded by a cap.
    """
    cycles = []
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in adjacency}
    path = []

    def dfs(node):
        if len(cycles) >= 25:
            return
        color[node] = GRAY
        path.append(node)
        for nxt in adjacency.get(node, []):
            if len(cycles) >= 25:
                break
            if color.get(nxt, WHITE) == GRAY:
                start = path.index(nxt)
                cycles.append(path[start:] + [nxt])
            elif color.get(nxt, WHITE) == WHITE:
                dfs(nxt)
        path.pop()
        color[node] = BLACK

    for n in list(adjacency.keys()):
        if color[n] == WHITE:
            dfs(n)
    return cycles


@router.get("/{batch_id}/dependency-graph")
def dependency_graph(batch_id: str, db: Session = Depends(get_db)):
    """
    Cross-file dependency graph for a project batch (Phase 7). Two layers,
    both derived on demand from already-stored scan rows -- no new model,
    no schema change:

      - FILE layer: local #include "..." relationships between the scanned
        files (regex-based, local includes only -- <system.h> headers are
        intentionally excluded since they aren't part of the project).
      - FUNCTION layer: per-file call graphs (existing
        code_intelligence.build_call_graph) plus best-effort CROSS-FILE
        edges, resolved by matching a called-but-undefined name in file A
        against a function actually defined in file B within the same
        batch. This is a heuristic (no real linker), so it can't detect
        e.g. static functions shadowing across files -- flagged as such
        in the response.
    """
    records = db.query(ScanRecord).filter(ScanRecord.batch_id == batch_id).order_by(ScanRecord.created_at).all()
    if not records:
        raise HTTPException(status_code=404, detail="Project batch not found")

    # -- FILE layer: #include-based edges --------------------------------
    file_nodes = []
    filenames_by_basename = {}
    for r in records:
        base = r.filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        filenames_by_basename.setdefault(base, r.filename)
        file_nodes.append({
            "id": r.filename, "label": base, "type": "file",
            "risk_level": r.risk_level, "vuln_probability": r.vuln_probability,
        })

    file_edges = []
    file_adjacency = {r.filename: [] for r in records}
    for r in records:
        for inc in _INCLUDE_RE.findall(r.code or ""):
            inc_base = inc.rsplit("/", 1)[-1]
            target = filenames_by_basename.get(inc_base)
            if target and target != r.filename:
                file_edges.append({"source": r.filename, "target": target, "label": "#include"})
                file_adjacency[r.filename].append(target)

    file_cycles = _find_cycles(file_adjacency)

    # -- FUNCTION layer: per-file call graphs + cross-file resolution ----
    function_nodes = []
    function_edges = []
    func_owner = {}       # function name -> filename that defines it
    per_file_intel = {}   # filename -> code_intelligence.analyze() result

    for r in records:
        intel = analysis_cache.get_intel(r)
        per_file_intel[r.filename] = intel
        if not intel.get("available"):
            continue
        for f in intel["functions"]:
            func_owner[f["name"]] = r.filename

    func_adjacency = {}
    for r in records:
        intel = per_file_intel.get(r.filename, {})
        if not intel.get("available"):
            continue
        base = r.filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        for f in intel["functions"]:
            node_id = f"{r.filename}::{f['name']}"
            function_nodes.append({
                "id": node_id, "label": f["name"], "type": "internal", "file": r.filename,
                "kind": "dangerous" if f["dangerous_apis"] else ("complex" if f["cyclomatic_complexity"] >= 8 else "normal"),
                "risk_level": r.risk_level,
                "pointer_ops": f["pointer_ops"], "global_refs": f.get("global_refs", []),
                "is_recursive": f["is_recursive"], "loc": f["loc"], "dangerous_apis": f["dangerous_apis"],
            })
            func_adjacency[node_id] = []
            for callee in f["calls"]:
                if callee == f["name"]:
                    continue  # recursion, not a cross-node dependency edge
                owner = func_owner.get(callee)
                if owner and owner != r.filename:
                    target_id = f"{owner}::{callee}"
                    function_edges.append({
                        "source": node_id, "target": target_id, "label": f"{base} -> {callee}()", "cross_file": True,
                    })
                elif owner == r.filename:
                    target_id = f"{owner}::{callee}"
                    function_edges.append({"source": node_id, "target": target_id, "cross_file": False})
                # else: external/library call -- omitted from this cross-file graph
                #       (already visible in the per-file Call Graph page).

    for e in function_edges:
        func_adjacency.setdefault(e["source"], []).append(e["target"])
    function_cycles = _find_cycles(func_adjacency)

    cross_file_edge_count = sum(1 for e in function_edges if e.get("cross_file"))

    return {
        "batch_id": batch_id,
        "project_name": records[0].project_name,
        "file_nodes": file_nodes,
        "file_edges": file_edges,
        "file_cycles": file_cycles,
        "function_nodes": function_nodes,
        "function_edges": function_edges,
        "function_cycles": function_cycles,
        "stats": {
            "total_files": len(records),
            "total_functions": len(function_nodes),
            "cross_file_edges": cross_file_edge_count,
            "file_cycles_detected": len(file_cycles),
            "function_cycles_detected": len(function_cycles),
        },
        "note": "Cross-file call resolution is a best-effort name match, not a real linker -- it cannot distinguish two static functions with the same name in different files.",
    }


# Dangerous APIs that write into a caller-supplied destination buffer --
# these get the more specific "writes" edge instead of the generic "uses"
# edge. Everything else in DANGEROUS_APIS (process/resource APIs like
# system, popen, alloca, or the alloc/free family handled separately below)
# keeps "uses".
_WRITE_APIS = {"strcpy", "strcat", "gets", "sprintf", "vsprintf", "memcpy", "memmove", "strncpy", "scanf"}


@router.get("/{batch_id}/knowledge-graph")
def knowledge_graph(batch_id: str, db: Session = Depends(get_db)):
    """
    Security Knowledge Graph (Phase 6). Unifies everything the pipeline
    already knows about a project into one typed graph -- Repository,
    Folder, File, Function, Variable, Pointer, Buffer, Memory, Dangerous
    API, CWE, and Prediction as nodes; contains / calls / reads / writes /
    allocates / frees / causes / related_to as edges. Every node and edge
    is backed by real per-file code_intelligence.analyze() output (the same
    function used by AI Code Explanation, Call Graph Explorer, and
    Dependency Graph) -- nothing here is a placeholder concept node with
    fabricated counts. "reads"/"writes"/"allocates"/"frees" are narrower,
    more specific edges carved out of the same evidence that used to be
    grouped under "uses" (global variable references, destination-buffer
    write APIs, and alloc/free call sites resolved to their containing
    function by line range).
    """
    records = db.query(ScanRecord).filter(ScanRecord.batch_id == batch_id).order_by(ScanRecord.created_at).all()
    if not records:
        raise HTTPException(status_code=404, detail="Project batch not found")

    nodes = {}   # id -> node dict (dedup by id)
    edges = []
    func_owner = {}

    def add_node(node_id, label, kind, **extra):
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "label": label, "kind": kind, **extra}
        return node_id

    def add_edge(source, target, relation):
        edges.append({"source": source, "target": target, "relation": relation})

    # ── Repository root ───────────────────────────────────────────────────
    repo_id = f"repo::{batch_id}"
    add_node(repo_id, records[0].project_name, "repository", total_files=len(records))

    # ── Folder tree (one node per path segment, contains-linked) ───────────
    folder_ids = {}   # folder path ("src/core") -> node id

    def ensure_folder(path_parts):
        """path_parts is the list of folder segments above the file itself."""
        parent_id = repo_id
        acc = ""
        for part in path_parts:
            acc = f"{acc}/{part}" if acc else part
            fid = f"folder::{batch_id}::{acc}"
            if acc not in folder_ids:
                folder_ids[acc] = fid
                add_node(fid, part, "folder", path=acc)
                add_edge(parent_id, fid, "contains")
            parent_id = folder_ids[acc]
        return parent_id

    per_file_intel = {}
    for r in records:
        intel = analysis_cache.get_intel(r)
        per_file_intel[r.filename] = intel
        if intel.get("available"):
            for f in intel["functions"]:
                func_owner[f["name"]] = r.filename

    for r in records:
        parts = re.split(r"[\\/]", r.filename)
        base = parts[-1]
        parent_id = ensure_folder(parts[:-1])
        add_node(r.filename, base, "file", risk_level=r.risk_level, vuln_probability=r.vuln_probability, scan_id=r.id)
        add_edge(parent_id, r.filename, "contains")

        # Prediction node -- the model's own verdict for this file, wired
        # into the graph so it can be explored alongside the evidence that
        # informed it (functions, dangerous APIs, CWEs beneath the file).
        pred_id = f"pred::{r.filename}"
        add_node(
            pred_id, f"{r.risk_level} ({r.vuln_probability:.0f}%)", "prediction",
            verdict=r.verdict, vuln_probability=r.vuln_probability, confidence=r.confidence, risk_level=r.risk_level, scan_id=r.id,
        )
        add_edge(r.filename, pred_id, "related_to")

        intel = per_file_intel.get(r.filename, {})
        if not intel.get("available"):
            continue

        if intel.get("pointers", {}).get("pointer_variables", 0) > 0:
            ptr_id = f"ptr::{r.filename}"
            add_node(ptr_id, f"Pointers ({base})", "pointer", count=intel["pointers"]["pointer_variables"], coverage=intel["pointers"]["null_check_coverage_pct"])
            add_edge(r.filename, ptr_id, "related_to")

        mem = intel.get("memory", {})
        mem_id = None
        if mem.get("allocations", 0) > 0 or mem.get("frees", 0) > 0:
            mem_id = f"mem::{r.filename}"
            add_node(mem_id, f"Memory ({base})", "memory", allocations=mem.get("allocations", 0), frees=mem.get("frees", 0), leak_risk=bool(mem.get("potential_leak")))
            add_edge(r.filename, mem_id, "related_to")

        for buf in intel.get("buffers", []):
            buf_id = f"buf::{r.filename}::{buf['name']}::{buf['line']}"
            add_node(buf_id, f"{buf['name']} [{buf['declared_size']}]", "buffer", line=buf["line"], file=r.filename)
            add_edge(r.filename, buf_id, "contains")

        for f in intel["functions"]:
            fn_id = f"{r.filename}::{f['name']}"
            fn_end = f["start_line"] + f["loc"]
            add_node(fn_id, f["name"], "function", file=r.filename, loc=f["loc"], complexity=f["cyclomatic_complexity"])
            add_edge(r.filename, fn_id, "contains")

            for callee in f["calls"]:
                if callee == f["name"]:
                    continue
                owner = func_owner.get(callee)
                if owner:
                    add_edge(fn_id, f"{owner}::{callee}", "calls")

            for api in f["dangerous_apis"]:
                api_id = f"api::{api}"
                add_node(api_id, api, "dangerous_api")
                add_edge(fn_id, api_id, "writes" if api in _WRITE_APIS else "uses")
                sev, cwe, _desc = code_intelligence.DANGEROUS_APIS.get(api, (0, None, None))
                if cwe:
                    entry = knowledge_base.lookup(cwe)
                    cwe_id = f"cwe::{cwe}"
                    add_node(cwe_id, f"{cwe}", "cwe", name=entry["name"], severity=entry["severity"])
                    add_edge(api_id, cwe_id, "causes")

            for g in f.get("global_refs", []):
                var_id = f"var::{r.filename}::{g}"
                add_node(var_id, g, "variable", file=r.filename)
                add_edge(fn_id, var_id, "reads")

            for buf in intel.get("buffers", []):
                if f["start_line"] <= buf["line"] <= fn_end:
                    buf_id = f"buf::{r.filename}::{buf['name']}::{buf['line']}"
                    add_edge(fn_id, buf_id, "uses")

            if mem_id:
                if any(f["start_line"] <= a["line"] <= fn_end for a in mem.get("alloc_sites", [])):
                    add_edge(fn_id, mem_id, "allocates")
                if any(f["start_line"] <= a["line"] <= fn_end for a in mem.get("free_sites", [])):
                    add_edge(fn_id, mem_id, "frees")

    kind_counts = {}
    for n in nodes.values():
        kind_counts[n["kind"]] = kind_counts.get(n["kind"], 0) + 1

    return {
        "batch_id": batch_id,
        "project_name": records[0].project_name,
        "nodes": list(nodes.values()),
        "edges": edges,
        "kind_counts": kind_counts,
    }
