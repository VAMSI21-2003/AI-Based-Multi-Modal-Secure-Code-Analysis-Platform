# CHAPTER 6: SOFTWARE TESTING

## 6.1 Testing Strategies

### 6.1.1 Unit Testing

Backend unit tests (pytest, `backend/tests/`) cover individual functions and modules in isolation:
feature-extraction dimensionality and correctness (`test_feature_extraction.py`), the fusion-alignment
logic itself (`tests/test_fusion_alignment.py`, at the repository root — deliberately kept separate
from `backend/tests/` since it tests the offline pipeline's fusion code, not the API), SSRF-protection
URL validation (`test_ssrf_protection.py`), and path-traversal/zip-bomb protections on batch upload
(`test_batch_upload_security.py`). Frontend unit tests (Vitest) cover individual utility functions and
components, e.g. `frontend/src/utils/risk.test.ts`.

### 6.1.2 Integration Testing

Tests that exercise a full FastAPI request/response cycle against a real (test) database session are
grouped separately from pure unit tests: `test_apply_patch.py` (the full Apply-Patch → Re-Scan HTTP
flow), `test_ci_scan.py` (the CI security-scan pipeline against fixture files, including SARIF-document
structural validity), `test_dependency_graph.py`, `test_derived_scan_schema.py`, and
`test_github_batch_meta.py`.

### 6.1.3 System Testing

`test_ml_pipeline.py` and `test_per_function_inference.py` exercise the system end-to-end through the
actual `/api/scan/*` endpoints, including the per-function-splitting behavior described in Chapter 5.2.4
(verifying a vulnerable function late in a large file is still detected, and that a file's verdict is
the true maximum across its functions rather than an average). `frontend/src/pages/Dashboard.test.tsx`
verifies, at the system level, that the Dashboard page renders real fetched statistics rather than any
placeholder/fabricated data — a small but notable detail given this report's own emphasis on not
presenting fabricated figures as real ones.

## 6.2 Test Cases

### 6.2.1 Sample Test Cases with Expected vs. Actual Results

The full backend/root suite was executed for this report on 2026-07-24 via `pytest backend/tests
tests`, and the frontend suite via `vitest run`. All results below are the actual, real output of that
run — not illustrative.

**Table 6.1: Sample test cases with expected vs. actual results**

| # | Test case | Expected result | Actual result |
|---|---|---|---|
| 1 | `test_ast_features_have_exactly_11_dimensions` | AST feature vector has exactly 11 keys | Passed |
| 2 | `test_metric_features_have_exactly_13_dimensions` | Metrics feature vector has exactly 13 keys | Passed |
| 3 | `test_fusion_vector_has_exactly_792_dimensions_in_the_trained_order` | Fused live-inference vector is 792-d, in AST→metrics→embedding order | Passed |
| 4 | `test_ast_extraction_survives_malformed_source_without_crashing` | Malformed/unparseable C code returns zeroed features, not an exception | Passed |
| 5 | `test_prediction_is_deterministic_for_the_same_input` | Same input code yields the same prediction on repeated calls | Passed |
| 6 | `test_verdict_threshold_matches_the_validated_constant` | Live verdict logic uses the validated 0.26 decision threshold | Passed |
| 7 | `test_file_level_verdict_is_the_true_max_across_functions_not_an_average` | Multi-function file verdict equals its riskiest function's verdict | Passed |
| 8 | `test_apply_patch_with_unknown_destination_size_is_blocked_not_silently_applied` | Apply-patch on an unresolvable buffer size returns HTTP 422, not a silent partial fix | Passed |
| 9 | `test_apply_patch_with_known_safe_destination_creates_derived_record_with_real_score` | A safe, resolvable rewrite creates a derived scan with a genuine re-computed score | Passed |
| 10 | `test_validate_url_rejects_literal_cloud_metadata_ip` | GitHub-scan URL validation rejects a literal cloud-metadata IP (SSRF protection) | Passed |
| 11 | `test_batch_upload_rejects_zip_with_too_many_members` | An oversized zip archive is rejected rather than exhausting server resources | Passed |
| 12 | `test_fully_aligned_tables_fuse_correctly` | Fusion of correctly aligned AST/metrics/CodeBERT tables produces correct rows | Passed |
| 13 | `test_shuffled_row_order_produces_identical_fused_result` | Fusion result is independent of each table's row order (regression test for the original alignment bug, Chapter 3.4.4) | Passed |
| 14 | `test_cross_table_label_mismatch_is_detected_and_raises` | A deliberately mismatched label across tables raises an error instead of silently fusing | Passed |
| 15 | `renders the real fetched stats, not fabricated data` (Dashboard.test.tsx) | Dashboard shows live API data, not placeholder values | Passed |

**Table 6.2: Full test suite totals (real, from this run)**

| Suite | Test files | Tests | Passed | Failed |
|---|---|---|---|---|
| Backend (pytest: `backend/tests/` + root `tests/`) | 15 | 110 | 110 | 0 |
| Frontend (Vitest) | 2 | 9 | 9 | 0 |
| **Total** | **17** | **119** | **119** | **0** |

## 6.3 Performance Metrics and Evaluation

The confusion matrix, precision/recall/F1, and accuracy figures for the trained classifiers are
reported in full in Chapter 7 (Results and Discussion), where they are presented alongside the
discussion of the feature-fusion alignment defect that was found and corrected before these numbers
were produced (Chapter 3.4.4). They are not repeated here to avoid the two chapters drifting out of
sync; Chapter 7 is the single source for these figures within this report, consistent with
`models/training_metadata.json` being the single source of truth in the underlying project.
