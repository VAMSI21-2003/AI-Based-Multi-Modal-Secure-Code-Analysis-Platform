# =============================================================================
# test_optimization_analyzer.py -- real tests for the 5 deterministic
# performance/efficiency heuristics in optimization_analyzer.py (see
# docs/OPTIMIZATION_SUGGESTIONS_DESIGN.md). One known-inefficient fixture
# that should trip all 5 checks, one known-clean fixture that should trip
# none of them.
# =============================================================================

from fastapi.testclient import TestClient

import optimization_analyzer as oa
from main import app

client = TestClient(app)

INEFFICIENT = """
#include <stdlib.h>
#include <string.h>

struct Point {
    int x;
    int y;
    int z;
    int w;
    int v;
};

int scan_buffer(char *buf) {
    int i;
    int total = 0;
    for (i = 0; i < strlen(buf); i++) {
        total += buf[i];
    }
    return total;
}

void build_message(char *msg, const char *word) {
    int i;
    for (i = 0; i < 5; i++) {
        strcat(msg, word);
    }
}

int *grow_array(int *arr, int n) {
    int i;
    for (i = 0; i < n; i++) {
        arr = realloc(arr, i + 1);
    }
    return arr;
}

void fill_buffer(int n) {
    int i;
    int *tmp;
    for (i = 0; i < n; i++) {
        tmp = malloc(sizeof(int));
        free(tmp);
    }
}

void process_point(struct Point p) {
    (void)p;
}
"""

# Same shapes, idiomatically correct: strlen() hoisted before the loop,
# sprintf() writes at a tracked offset (msg + offset) instead of appending
# to the same fixed destination, no malloc/realloc call is ever placed
# inside a loop (exact-size allocation done once), and the struct parameter
# has only 2 members (<= the >4 threshold).
CLEAN = """
#include <stdlib.h>
#include <string.h>

struct Small {
    int x;
    int y;
};

int scan_buffer(char *buf) {
    int i;
    int total = 0;
    int len = strlen(buf);
    for (i = 0; i < len; i++) {
        total += buf[i];
    }
    return total;
}

void build_message(char *msg, const char *word) {
    int offset = 0;
    int i;
    for (i = 0; i < 5; i++) {
        offset += sprintf(msg + offset, "%s", word);
    }
}

int *alloc_exact(int n) {
    int *arr = malloc(sizeof(int) * n);
    return arr;
}

void process_point(struct Small p) {
    (void)p;
}
"""


def test_inefficient_fixture_trips_all_five_checks():
    result = oa.analyze(INEFFICIENT)
    assert result["available"] is True
    assert result["heuristic_based"] is True

    assert len(result["loop_invariant_length_calls"]) == 1
    assert result["loop_invariant_length_calls"][0]["variable"] == "buf"

    assert len(result["string_growth_in_loop"]) == 1
    assert result["string_growth_in_loop"][0]["api"] == "strcat"
    assert result["string_growth_in_loop"][0]["destination"] == "msg"

    assert len(result["linear_realloc_growth"]) == 1
    assert result["linear_realloc_growth"][0]["size_expression"] == "i + 1"

    # realloc() (grow_array) and malloc() (fill_buffer) are each inside
    # their own loop -- two distinct review-flag findings, one per loop.
    assert len(result["heap_alloc_in_loop"]) == 2
    apis = {a["api"] for f in result["heap_alloc_in_loop"] for a in f["allocations"]}
    assert apis == {"realloc", "malloc"}

    assert len(result["large_struct_by_value"]) == 1
    assert result["large_struct_by_value"][0]["struct_name"] == "Point"
    assert result["large_struct_by_value"][0]["member_count"] == 5

    assert result["total_findings"] == 6


def test_clean_fixture_trips_no_checks():
    result = oa.analyze(CLEAN)
    assert result["available"] is True
    assert result["heuristic_based"] is True
    assert result["loop_invariant_length_calls"] == []
    assert result["string_growth_in_loop"] == []
    assert result["linear_realloc_growth"] == []
    assert result["heap_alloc_in_loop"] == []
    assert result["large_struct_by_value"] == []
    assert result["total_findings"] == 0


def test_empty_code_is_available_with_no_findings():
    result = oa.analyze("")
    assert result["available"] is True
    assert result["total_findings"] == 0


def test_findings_are_never_merged_into_a_risk_or_probability_field():
    result = oa.analyze(INEFFICIENT)
    # This module must never compute or expose anything resembling the ML
    # risk score -- it is a separate, deterministic, heuristic layer.
    forbidden_keys = {"vuln_probability", "risk_level", "risk_score"}
    assert forbidden_keys.isdisjoint(result.keys())


def test_optimization_endpoint_is_wired_into_the_real_scan_flow():
    # End-to-end: POST a real scan through the same /api/scan/code path
    # every other scan entry point (batch/ZIP/GitHub) also funnels through,
    # then fetch its optimization findings via the new endpoint -- proves
    # this reuses the existing ScanRecord infrastructure rather than a
    # parallel pipeline, per docs/OPTIMIZATION_SUGGESTIONS_DESIGN.md §2.
    post_resp = client.post("/api/scan/code", json={
        "code": INEFFICIENT, "project_name": "opt-test", "filename": "inefficient.c",
        "model_choice": "XGBoost", "source": "paste",
    })
    assert post_resp.status_code == 200
    scan_id = post_resp.json()["id"]

    get_resp = client.get(f"/api/scan/{scan_id}/optimization")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["heuristic_based"] is True
    assert body["total_findings"] == 6
    assert "vuln_probability" not in body
