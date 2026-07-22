# =============================================================================
# analysis_cache.py -- in-process cache for expensive per-file derived
# analysis (code_intelligence.analyze(), ml_bridge.line_risk_scan()) that
# routers/project.py's aggregation endpoints (project_summary,
# dependency_graph, knowledge_graph) were re-running from scratch on EVERY
# request, for EVERY file in a batch -- measured at ~2-5s for a 67-file
# batch, entirely recomputation, on every single dashboard refresh.
#
# Cache key: ScanRecord.id. This is safe because `code` and `vuln_probability`
# are set exactly once, at scan-creation time, in scan_service.run_and_store_scan
# -- verified (grep) that no code path anywhere in this backend ever reassigns
# either field afterwards. A record's derived analysis therefore never goes
# stale for the lifetime of that record; there is nothing to invalidate.
#
# Bounded size (not unbounded growth): a simple dict is fine for this
# project's scale (a single-process research/demo backend, not a multi-tenant
# service), but is capped and FIFO-evicted defensively so a very long-running
# process scanning many large repositories doesn't grow memory without bound.
# =============================================================================

from collections import OrderedDict

import code_intelligence
import ml_bridge
import optimization_analyzer

_MAX_ENTRIES = 20_000

_intel_cache: "OrderedDict[str, dict]" = OrderedDict()
_line_risk_cache: "OrderedDict[str, list]" = OrderedDict()
_optimization_cache: "OrderedDict[str, dict]" = OrderedDict()


def _put(cache: "OrderedDict", key: str, value):
    cache[key] = value
    cache.move_to_end(key)
    if len(cache) > _MAX_ENTRIES:
        cache.popitem(last=False)


def get_intel(record) -> dict:
    cached = _intel_cache.get(record.id)
    if cached is not None:
        _intel_cache.move_to_end(record.id)
        return cached
    result = code_intelligence.analyze(record.code, vuln_probability=record.vuln_probability or 0.0)
    _put(_intel_cache, record.id, result)
    return result


def get_line_risks(record) -> list:
    cached = _line_risk_cache.get(record.id)
    if cached is not None:
        _line_risk_cache.move_to_end(record.id)
        return cached
    result = ml_bridge.line_risk_scan(record.code)
    _put(_line_risk_cache, record.id, result)
    return result


def get_optimization_findings(record) -> dict:
    cached = _optimization_cache.get(record.id)
    if cached is not None:
        _optimization_cache.move_to_end(record.id)
        return cached
    result = optimization_analyzer.analyze(record.code)
    _put(_optimization_cache, record.id, result)
    return result


def cache_sizes() -> dict:
    """For tests/diagnostics only."""
    return {
        "intel_entries": len(_intel_cache),
        "line_risk_entries": len(_line_risk_cache),
        "optimization_entries": len(_optimization_cache),
    }
