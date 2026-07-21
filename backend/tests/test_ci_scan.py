# =============================================================================
# test_ci_scan.py -- tests for backend/ci_scan.py, the headless CI entrypoint.
#
# A note on what "known-clean fixture -> expect no finding" can honestly mean
# here: app/predictor.py's VULNERABILITY_THRESHOLD (0.26) was deliberately
# selected to maximize recall (97.7% on the corrected test set, see
# docs/ML_ALIGNMENT_FIX_RESULTS.md Section 7) -- by design, the trained model
# flags MOST inputs, including tiny/simple/synthetic ones, as "VULNERABLE" at
# some (often LOW) risk level. That is real, already-disclosed model
# behavior, not a bug in ci_scan.py, so these tests do NOT assert that a
# clean snippet gets an overall "NOT VULNERABLE"/"SAFE" verdict -- that would
# be asserting something the model itself doesn't guarantee and would make
# this test flaky/dishonest. What IS deterministic and safe to assert: the
# separate, rule-based evidence layer (ml_bridge.line_risk_scan, the same
# CWE-tagged pattern scanner the live app uses) finds a real match for a
# genuinely dangerous pattern and finds none for a genuinely clean one.
# =============================================================================

import json
import os

import ci_scan

VULNERABLE_FIXTURE = """void copy_input(char *dest, const char *src) {
    strcpy(dest, src);
}
"""

CLEAN_FIXTURE = """int add_two(int a, int b) {
    return a + b;
}
"""


def test_scan_one_file_finds_a_cwe_finding_for_a_known_vulnerable_fixture(tmp_path):
    fixture = tmp_path / "vulnerable.c"
    fixture.write_text(VULNERABLE_FIXTURE, encoding="utf-8")

    result = ci_scan.scan_one_file(str(fixture), str(tmp_path), "XGBoost")

    assert result is not None
    cwe_findings = [f for f in result["findings"] if f["cwe"]]
    assert len(cwe_findings) >= 1
    assert "CWE-120" in cwe_findings[0]["cwe"]
    assert cwe_findings[0]["function"] == "copy_input"
    assert result["combined_risk_level"] in ("HIGH RISK", "CRITICAL")
    assert result["escalated_by_evidence"] is True
    assert result["model_mode"] in ("trained", "fallback")


def test_scan_one_file_finds_no_cwe_evidence_for_a_known_clean_fixture(tmp_path):
    fixture = tmp_path / "clean.c"
    fixture.write_text(CLEAN_FIXTURE, encoding="utf-8")

    result = ci_scan.scan_one_file(str(fixture), str(tmp_path), "XGBoost")

    assert result is not None
    cwe_findings = [f for f in result["findings"] if f["cwe"]]
    assert cwe_findings == []


def test_load_files_from_list_filters_extensions_and_skips_missing_files(tmp_path):
    (tmp_path / "real.c").write_text("int x;\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("hello\n", encoding="utf-8")
    file_list = tmp_path / "changed_files.txt"
    file_list.write_text("real.c\nnotes.md\ndoes_not_exist.c\n", encoding="utf-8")

    found = list(ci_scan.load_files_from_list(str(file_list), str(tmp_path)))

    assert len(found) == 1
    assert found[0].endswith("real.c")


def test_load_files_from_list_resolves_paths_relative_to_base_dir(tmp_path):
    sub = tmp_path / "src" / "nested"
    sub.mkdir(parents=True)
    (sub / "deep.c").write_text("int x;\n", encoding="utf-8")
    file_list = tmp_path / "changed_files.txt"
    file_list.write_text("src/nested/deep.c\n", encoding="utf-8")

    found = list(ci_scan.load_files_from_list(str(file_list), str(tmp_path)))

    assert len(found) == 1
    assert os.path.isfile(found[0])


def test_build_function_index_maps_a_line_to_its_enclosing_function():
    index = ci_scan.build_function_index(VULNERABLE_FIXTURE)
    assert index != []
    name = ci_scan.function_at_line(index, 2)
    assert name == "copy_input"
    assert ci_scan.function_at_line(index, 999) is None


def test_to_sarif_produces_a_structurally_valid_minimal_sarif_2_1_0_document(tmp_path):
    fixture = tmp_path / "vulnerable.c"
    fixture.write_text(VULNERABLE_FIXTURE, encoding="utf-8")
    result = ci_scan.scan_one_file(str(fixture), str(tmp_path), "XGBoost")

    sarif = ci_scan.to_sarif([result], str(tmp_path))

    assert sarif["version"] == "2.1.0"
    assert "$schema" in sarif
    assert len(sarif["runs"]) == 1
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"]
    rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert len(run["results"]) >= 1
    for res in run["results"]:
        assert res["ruleId"] in rule_ids
        assert res["level"] in ("none", "note", "warning", "error")
        assert "text" in res["message"]
        loc = res["locations"][0]["physicalLocation"]
        assert loc["artifactLocation"]["uri"]
        assert loc["region"]["startLine"] >= 1


def test_blocking_defaults_to_false_when_env_var_is_unset(monkeypatch):
    monkeypatch.delenv("SCAN_BLOCKING", raising=False)
    assert ci_scan._env_flag("SCAN_BLOCKING", default=False) is False


def test_blocking_env_var_is_honored_when_set_true(monkeypatch):
    monkeypatch.setenv("SCAN_BLOCKING", "true")
    assert ci_scan._env_flag("SCAN_BLOCKING", default=False) is True


def test_load_baseline_status_reads_the_real_committed_status_file():
    # models/ml_baseline_status.json is a real, committed, small status
    # record (not a mock) -- this guards against ci_scan.py's path
    # resolution silently breaking if the file is ever moved.
    status = ci_scan.load_baseline_status()
    assert status is not None
    assert status["fusion_alignment_status"] == "fixed"
    assert status["baseline_go_no_go"] == "GO"


def test_full_scan_of_the_demo_fixtures_writes_valid_json_and_sarif(tmp_path):
    demo_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "demo", "scan_samples")
    output_base = str(tmp_path / "report")

    import sys
    old_argv = sys.argv
    try:
        sys.argv = ["ci_scan.py", "--path", demo_dir, "--output", output_base, "--no-fail"]
        ci_scan.main()
    finally:
        sys.argv = old_argv

    with open(f"{output_base}.json", encoding="utf-8") as fh:
        summary = json.load(fh)
    assert summary["total_files"] == 2
    assert summary["model_mode"] in ("trained", "fallback", "mixed")
    assert summary["ml_baseline_status_line"].startswith("GO")

    with open(f"{output_base}.sarif", encoding="utf-8") as fh:
        sarif = json.load(fh)
    assert sarif["version"] == "2.1.0"
