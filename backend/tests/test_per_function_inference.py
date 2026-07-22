# =============================================================================
# test_per_function_inference.py -- regression tests for per-function live
# inference (docs/PER_FUNCTION_INFERENCE_DESIGN.md).
#
# The core claim being tested: whole-file scanning silently truncated
# CodeBERT's input at 512 tokens, so a vulnerable function positioned late
# in a large file could be entirely outside what the model ever saw. These
# tests prove the fix using real token counts from the real tokenizer, not
# fragile assertions about the model's own probability output (this
# project's own audits found the trained classifier has real, documented
# quirks -- e.g. scoring a "safer" rewrite higher-risk than the original,
# see docs/CI_CD.md #4 -- so asserting an exact probability here would be
# testing the classifier's judgment, not the truncation fix).
# =============================================================================

import ml_bridge
import predictor


def _make_large_file_with_late_vulnerability(n_padding_functions: int = 40) -> tuple:
    """
    Builds a synthetic file: N safe, boring padding functions followed by
    one function with an unbounded strcpy() call at the very end -- placed
    late enough that the whole file exceeds CodeBERT's 512-token limit
    well before reaching it.
    """
    padding = "".join(f"""
int safe_add_{i}(int a, int b) {{
    int result = a + b;
    if (result > 1000) {{
        result = 1000;
    }}
    return result;
}}
""" for i in range(n_padding_functions))

    vulnerable_fn = """
void copy_input(char *dest, const char *src) {
    strcpy(dest, src);
}
"""
    return padding + vulnerable_fn, vulnerable_fn, padding


def test_fixture_actually_exceeds_the_token_limit_before_reaching_the_vulnerability():
    # Sanity-checks the fixture itself against the real tokenizer, so the
    # test below is provably exercising the scenario it claims to.
    whole_file, vulnerable_fn, padding = _make_large_file_with_late_vulnerability()
    tokenizer, _ = ml_bridge.get_codebert()

    whole_tokens = tokenizer(whole_file, truncation=False)["input_ids"]
    padding_tokens = tokenizer(padding, truncation=False)["input_ids"]
    vuln_alone_tokens = tokenizer(vulnerable_fn, truncation=False)["input_ids"]

    assert len(whole_tokens) > 512, (
        f"fixture only has {len(whole_tokens)} whole-file tokens -- must exceed 512 "
        "to actually exercise the old whole-file truncation bug"
    )
    assert len(padding_tokens) > 512, (
        "the vulnerable function must start AFTER the 512-token truncation point, "
        f"but padding alone is only {len(padding_tokens)} tokens"
    )
    assert len(vuln_alone_tokens) < 512, (
        "the vulnerable function alone must fit comfortably within 512 tokens for "
        "per-function inference to see it untruncated"
    )


def test_vulnerable_function_late_in_a_large_file_is_still_analyzed_per_function():
    # The actual regression guard: run the real pipeline (ml_bridge.run_prediction,
    # the same function every scan entry point calls) against the fixture and
    # confirm the late vulnerable function was genuinely split out and analyzed
    # on its own, not silently dropped by whole-file truncation.
    whole_file, _, _ = _make_large_file_with_late_vulnerability()

    result = ml_bridge.run_prediction(whole_file, "XGBoost")

    assert result["functions_analyzed"] == 41  # 40 padding + 1 vulnerable
    assert result["function_results"] is not None

    names = [fr["name"] for fr in result["function_results"]]
    assert "copy_input" in names

    copy_input_result = next(fr for fr in result["function_results"] if fr["name"] == "copy_input")
    # This function's OWN embedding must have been computed from its own
    # (short, well within the token limit) text -- not zeroed out or
    # skipped because of where it sits in the whole file.
    assert copy_input_result["embedding_dims"] == 768


def test_file_level_verdict_is_the_true_max_across_functions_not_an_average():
    # Max-risk aggregation: the file-level verdict must equal whichever
    # function actually scored highest -- not an average across all 41
    # (which would come out much lower), and not assumed in advance to be
    # any particular named function. This fixture's own padding functions
    # turned out to include one that outscores the real strcpy()
    # vulnerability (a real instance of this project's own documented model
    # quirk -- see docs/CI_CD.md #4, where a structurally-simple "safe"
    # example scored higher risk than a genuinely unsafe one) -- which is
    # exactly why this test checks the aggregation MECHANISM (true max wins)
    # rather than asserting which specific function should win.
    whole_file, _, _ = _make_large_file_with_late_vulnerability()

    result = ml_bridge.run_prediction(whole_file, "XGBoost")
    probabilities = [fr["vuln_probability"] for fr in result["function_results"]]
    true_max = max(probabilities)

    assert result["vuln_probability"] == true_max
    # Deliberately not asserting max is far above the average here: this
    # model's decision threshold (0.26) was tuned for aggressive recall
    # (97.7% on the corrected test set, docs/ML_ALIGNMENT_FIX_RESULTS.md
    # #7), so a set of near-identical padding functions can legitimately
    # score close to each other and close to the real vulnerability -- that
    # is a property of the classifier, not something this aggregation-logic
    # test should assert on.


def test_mixed_file_one_vulnerable_among_several_safe_functions():
    # Smaller, more direct fixture requested for this regression: one
    # clearly vulnerable function among several clearly safe ones.
    code = """
void safe_helper_one(int x) {
    int y = x + 1;
}

void safe_helper_two(int a, int b) {
    int sum = a + b;
}

void copy_input(char *dest, const char *src) {
    strcpy(dest, src);
}

void safe_helper_three(int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += i;
    }
}
"""
    result = ml_bridge.run_prediction(code, "XGBoost")
    assert result["functions_analyzed"] == 4

    by_name = {fr["name"]: fr for fr in result["function_results"]}
    assert set(by_name) == {"safe_helper_one", "safe_helper_two", "copy_input", "safe_helper_three"}

    # copy_input must have been genuinely analyzed with a real embedding
    # (not skipped/truncated away) -- the actual regression this fixture
    # guards against.
    assert by_name["copy_input"]["embedding_dims"] == 768

    # The file-level (aggregated) verdict must equal the TRUE max across
    # all 4 functions' own results (max-risk aggregation, not an average) --
    # asserted against the true max rather than assuming copy_input is
    # necessarily it, since this project's own model has documented cases
    # where structurally-simple "safe" code scores higher than real
    # vulnerabilities (docs/CI_CD.md #4).
    true_max = max(fr["vuln_probability"] for fr in result["function_results"])
    assert result["vuln_probability"] == true_max


def test_functions_analyzed_is_zero_and_whole_code_path_used_when_no_functions_found():
    # Header-only / no function_definition nodes -- must fall back to the
    # original whole-code behavior, not error or silently return nothing.
    header_only = "extern int global_counter;\n#define MAX_SIZE 128\n"
    result = ml_bridge.run_prediction(header_only, "XGBoost")
    assert result["functions_analyzed"] == 0
    assert result["function_results"] is None
    # Falls back to predict_with_model's shape (still a valid verdict).
    assert result["verdict"] in ("VULNERABLE", "NOT VULNERABLE")


def test_batched_embeddings_match_single_item_embeddings_within_floating_point_tolerance():
    # Confirms batching doesn't change WHAT is computed, only how many
    # forward passes it takes -- batched output for N independent inputs
    # should equal running each one individually.
    import numpy as np

    tokenizer, codebert_model = ml_bridge.get_codebert()
    texts = [
        "int add(int a, int b) { return a + b; }",
        "void copy_input(char *dest, const char *src) { strcpy(dest, src); }",
        "int mul(int a, int b) { return a * b; }",
    ]

    batched = predictor.extract_codebert_embeddings_batch(texts, tokenizer, codebert_model)
    singles = np.stack([
        predictor.extract_codebert_embedding(t, tokenizer, codebert_model) for t in texts
    ])

    assert batched.shape == singles.shape == (3, 768)
    np.testing.assert_allclose(batched, singles, atol=1e-4)


def test_batching_chunks_large_function_counts_instead_of_one_giant_batch():
    # A file with more functions than BATCH_SIZE must still produce exactly
    # one embedding per function (chunked internally), not fail or truncate
    # the function list itself.
    tokenizer, codebert_model = ml_bridge.get_codebert()
    texts = [f"int f{i}(void) {{ return {i}; }}" for i in range(predictor.BATCH_SIZE * 2 + 3)]

    embeddings = predictor.extract_codebert_embeddings_batch(texts, tokenizer, codebert_model)
    assert embeddings.shape == (len(texts), 768)
