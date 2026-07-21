# =============================================================================
# test_dependency_graph.py -- regression tests for GET
# /api/project/{batch_id}/dependency-graph's function_nodes id assignment.
#
# code_intelligence._function_name() falls back to the literal string
# "anonymous" whenever a function's declarator can't be resolved (common with
# macro-heavy test frameworks) -- multiple such functions in the same file
# used to collide on node_id = f"{filename}::{name}" in routers/project.py,
# since function_nodes is a plain list with no dedup. React rejected this
# ("Encountered two children with the same key") when the Call Graph
# Explorer rendered these nodes; reproduced live against a real GitHub scan
# of https://github.com/DaveGamble/cJSON (its vendored Unity test framework
# has many same-named/"anonymous" functions per file) before this fix.
# =============================================================================

import io
import zipfile

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _zip_bytes(entries: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _scan_batch(entries: dict, project_name: str) -> str:
    response = client.post(
        "/api/scan/batch",
        data={"project_name": project_name, "model_choice": "XGBoost"},
        files={"files": ("repo.zip", _zip_bytes(entries), "application/zip")},
    )
    assert response.status_code == 200
    return response.json()["batch_id"]


def test_duplicate_function_names_in_one_file_get_disambiguated_ids():
    # Three functions literally named "foo" in the same file -- tree-sitter
    # parses this as three distinct function_definition nodes (syntax, not
    # semantics), which is exactly the shape of the real-world collision
    # (multiple "anonymous"-named functions per file).
    code = """
void foo(void) { int x = 1; }
void bar(void) { int y = 2; }
void foo(void) { int z = 3; }
void foo(void) { int w = 4; }
"""
    batch_id = _scan_batch({"dup_test.c": code}, "dependency-graph-collision-test")

    resp = client.get(f"/api/project/{batch_id}/dependency-graph")
    assert resp.status_code == 200
    ids = [n["id"] for n in resp.json()["function_nodes"]]

    assert len(ids) == len(set(ids)), f"duplicate node ids present: {ids}"
    assert ids == [
        "dup_test.c::foo",
        "dup_test.c::bar",
        "dup_test.c::foo#1",
        "dup_test.c::foo#2",
    ]


def test_unique_function_names_keep_the_original_plain_id_format():
    # Regression guard: files with no name collision must produce byte-
    # identical ids to before this fix (no "#0" or other suffix noise on the
    # common case).
    code = """
void alpha(void) { int a = 1; }
void beta(void) { int b = 2; }
void gamma(void) { int c = 3; }
"""
    batch_id = _scan_batch({"unique_test.c": code}, "dependency-graph-no-collision-test")

    resp = client.get(f"/api/project/{batch_id}/dependency-graph")
    assert resp.status_code == 200
    ids = [n["id"] for n in resp.json()["function_nodes"]]

    assert ids == ["unique_test.c::alpha", "unique_test.c::beta", "unique_test.c::gamma"]
    assert not any("#" in i for i in ids)
