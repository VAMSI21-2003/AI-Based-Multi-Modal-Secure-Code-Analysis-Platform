# =============================================================================
# test_analysis_cache.py -- real tests for the per-file analysis cache that
# fixed project_summary/dependency_graph/knowledge_graph recomputing
# code_intelligence.analyze() and ml_bridge.line_risk_scan() on every single
# request (measured before this fix: ~2-5s per request for a 67-file batch;
# after: ~0.01-0.05s on repeat/cross-endpoint requests to the same records).
# =============================================================================

import analysis_cache
from database import ScanRecord

VULNERABLE_SNIPPET = """
void copy_input(char *dest, const char *src) {
    strcpy(dest, src);
}
"""


def _fake_record(record_id: str, code: str, vuln_probability: float = 80.0):
    r = ScanRecord()
    r.id = record_id
    r.code = code
    r.vuln_probability = vuln_probability
    return r


def test_get_intel_returns_the_same_object_on_repeat_calls():
    record = _fake_record("cache-test-1", VULNERABLE_SNIPPET)
    first = analysis_cache.get_intel(record)
    second = analysis_cache.get_intel(record)
    # Identity, not just equality -- proves the second call short-circuited
    # to the cache instead of recomputing a fresh (but equal-valued) result.
    assert first is second


def test_get_line_risks_returns_the_same_object_on_repeat_calls():
    record = _fake_record("cache-test-2", VULNERABLE_SNIPPET)
    first = analysis_cache.get_line_risks(record)
    second = analysis_cache.get_line_risks(record)
    assert first is second


def test_different_records_get_independently_cached_results():
    r1 = _fake_record("cache-test-3a", VULNERABLE_SNIPPET, vuln_probability=90.0)
    r2 = _fake_record("cache-test-3b", "void safe(void) { return; }", vuln_probability=5.0)
    intel1 = analysis_cache.get_intel(r1)
    intel2 = analysis_cache.get_intel(r2)
    assert intel1 is not intel2
