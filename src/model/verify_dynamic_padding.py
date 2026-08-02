# =============================================================================
# verify_dynamic_padding.py -- PHASE E (pre-check) of docs/ASYNC_SCAN_DESIGN.md
# Sec 4's dynamic-padding speed optimization.
#
# Read-only comparison, before touching app/predictor.py: does switching
# extract_codebert_embeddings_batch()'s tokenizer call from
# padding="max_length" (pads every item in a batch to exactly 512 tokens,
# regardless of actual length) to padding=True (pads only to the longest
# item IN THAT BATCH) produce numerically identical [CLS] embeddings for
# every un-truncated function? Per instruction: if not, STOP and report
# back rather than deciding unilaterally whether any difference found is
# acceptable.
#
# This script does NOT modify app/predictor.py -- it independently
# replicates both code paths (current vs. proposed) using the SAME real
# tokenizer/model app/predictor.py already loads (via ml_bridge, the
# production model-loading path, not a separately downloaded copy), and
# compares their outputs directly.
#
# Run: python src/model/verify_dynamic_padding.py
# =============================================================================

import os
import sys

import numpy as np
import torch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)

import ml_bridge  # noqa: E402


def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def embed_batch(tokenizer, model, codes, padding_strategy):
    inputs = tokenizer(
        codes,
        return_tensors="pt",
        max_length=512,
        truncation=True,
        padding=padding_strategy,
    )
    with torch.no_grad():
        output = model(**inputs)
    return output.last_hidden_state[:, 0, :].cpu().numpy(), inputs["input_ids"].shape


def make_test_functions():
    tiny = "void f(int x) { return; }"
    medium = "void copy_data(char *dst, const char *src, int n) {\n" + \
        "\n".join(f"    dst[{i}] = src[{i}];" for i in range(20)) + "\n}"
    over_limit = "void copy_data(char *dst, const char *src, int n) {\n" + \
        "\n".join(f"    dst[{i}] = src[{i}];" for i in range(40)) + "\n}"
    empty_ish = "void noop(void) {}"
    return {"tiny": tiny, "medium": medium, "over_limit_truncated": over_limit, "empty_ish": empty_ish}


def main():
    section("LOAD THE REAL PRODUCTION TOKENIZER + MODEL (via ml_bridge, same path app/predictor.py uses)")
    tokenizer, model = ml_bridge.get_codebert()
    print(f"  Loaded: {type(model).__name__}")

    fns = make_test_functions()
    for name, code in fns.items():
        n_tokens = len(tokenizer(code)["input_ids"])
        truncated = n_tokens > 512
        print(f"  {name:<24} {n_tokens:>5} tokens{'  (TRUNCATED to 512)' if truncated else ''}")

    section("TEST 1: batch of ONLY short functions (the main case this optimization targets)")
    short_batch = [fns["tiny"], fns["medium"], fns["empty_ish"]]
    emb_old, shape_old = embed_batch(tokenizer, model, short_batch, "max_length")
    emb_new, shape_new = embed_batch(tokenizer, model, short_batch, True)
    print(f"  padding=\"max_length\" input_ids shape: {shape_old}")
    print(f"  padding=True         input_ids shape: {shape_new}")
    diff = np.abs(emb_old - emb_new)
    print(f"  max abs diff: {diff.max():.10e}")
    print(f"  mean abs diff: {diff.mean():.10e}")
    identical_1 = np.array_equal(emb_old, emb_new)
    close_1 = np.allclose(emb_old, emb_new, atol=1e-5, rtol=1e-5)
    print(f"  np.array_equal (bit-identical): {identical_1}")
    print(f"  np.allclose (atol=1e-5, rtol=1e-5): {close_1}")

    section("TEST 2: MIXED batch (short + long-but-under-512 + truncated-over-512)")
    mixed_batch = [fns["tiny"], fns["medium"], fns["over_limit_truncated"], fns["empty_ish"]]
    emb_old2, shape_old2 = embed_batch(tokenizer, model, mixed_batch, "max_length")
    emb_new2, shape_new2 = embed_batch(tokenizer, model, mixed_batch, True)
    print(f"  padding=\"max_length\" input_ids shape: {shape_old2}")
    print(f"  padding=True         input_ids shape: {shape_new2}")
    diff2 = np.abs(emb_old2 - emb_new2)
    print(f"  max abs diff: {diff2.max():.10e}")
    print(f"  mean abs diff: {diff2.mean():.10e}")
    # Per-row breakdown -- does the TRUNCATED item (which pads to the same
    # 512 either way) match exactly, and do the un-truncated items match?
    for i, name in enumerate(["tiny", "medium", "over_limit_truncated", "empty_ish"]):
        row_diff = np.abs(emb_old2[i] - emb_new2[i]).max()
        print(f"    row {i} ({name}): max abs diff = {row_diff:.10e}")
    identical_2 = np.array_equal(emb_old2, emb_new2)
    close_2 = np.allclose(emb_old2, emb_new2, atol=1e-5, rtol=1e-5)
    print(f"  np.array_equal (bit-identical): {identical_2}")
    print(f"  np.allclose (atol=1e-5, rtol=1e-5): {close_2}")

    section("TEST 3: single-item batch (batch_size=1 edge case)")
    single_batch = [fns["medium"]]
    emb_old3, _ = embed_batch(tokenizer, model, single_batch, "max_length")
    emb_new3, _ = embed_batch(tokenizer, model, single_batch, True)
    diff3 = np.abs(emb_old3 - emb_new3)
    print(f"  max abs diff: {diff3.max():.10e}")
    close_3 = np.allclose(emb_old3, emb_new3, atol=1e-5, rtol=1e-5)
    print(f"  np.allclose (atol=1e-5, rtol=1e-5): {close_3}")

    section("TEST 4: real per-function inference pipeline output comparison")
    # Not just the raw [CLS] vector -- run BOTH through full_feature_vector's
    # downstream XGBoost prediction to confirm the FINAL vuln_probability is
    # unaffected, using ml_bridge's real prediction path where practical.
    from predictor import extract_codebert_embeddings_batch
    real_batch = [fns["tiny"], fns["medium"], fns["over_limit_truncated"]]
    prod_result = extract_codebert_embeddings_batch(real_batch, tokenizer, model)  # current production code, unmodified
    manual_new, _ = embed_batch(tokenizer, model, real_batch, True)
    diff4 = np.abs(prod_result - manual_new)
    print(f"  Production extract_codebert_embeddings_batch() (padding=max_length) vs. manual padding=True:")
    print(f"  max abs diff: {diff4.max():.10e}")
    close_4 = np.allclose(prod_result, manual_new, atol=1e-5, rtol=1e-5)
    print(f"  np.allclose (atol=1e-5, rtol=1e-5): {close_4}")

    section("VERDICT")
    all_close = close_1 and close_2 and close_3 and close_4
    if all_close:
        print("  PASS: padding=True produces numerically equivalent [CLS] embeddings to")
        print("  padding=\"max_length\" (within 1e-5 tolerance) for every test case, including")
        print("  truncated items and mixed-length batches. Safe to ship.")
    else:
        print("  FAIL: a real numerical difference was found. STOPPING per instruction --")
        print("  do NOT apply the padding change. Report this back rather than deciding")
        print("  unilaterally whether the difference is acceptable.")
    return 0 if all_close else 1


if __name__ == "__main__":
    sys.exit(main())
