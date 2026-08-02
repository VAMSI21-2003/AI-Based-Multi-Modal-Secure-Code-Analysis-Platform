# =============================================================================
# embedding_pooling_experiment.py -- standalone experiment (no design doc):
# does mean-pooling over all CodeBERT token positions reduce embedding
# anisotropy compared to the [CLS]-token embedding production actually uses?
#
# Part 1: re-verify the previously-reported mean pairwise cosine similarity
#         of 0.9833 for [CLS] embeddings on 500 random functions, against the
#         CURRENT (alignment-corrected) dataset -- fresh forward pass through
#         the real production tokenizer/model (ml_bridge.get_codebert()), not
#         a re-read of the old number or of final_features.csv's cached
#         embed_ columns (those were computed by the same original pipeline
#         this is meant to independently check).
# Part 2: for the SAME 500 sampled functions, compute mean-pooled embeddings
#         (mean over token positions, respecting attention_mask, i.e.
#         excluding padding) from the SAME forward pass (same hidden states,
#         just a different reduction over the sequence dimension -- the
#         cleanest possible apples-to-apples comparison) and measure the same
#         mean pairwise cosine similarity metric.
# Part 3 (conditional): only runs if Part 2 shows a meaningful anisotropy
#         reduction. If so, computes mean-pooled embeddings for the FULL
#         dataset and retrains XGBoost (same hyperparameters, same single
#         80/20 stratified split as modality_ablation.py / production) on a
#         fused feature set using mean-pooled embeddings instead of [CLS],
#         compared against the production baseline (F1=0.5391, AUC=0.6346).
#
# Does NOT touch extraction, fuse_features.py, fusion_core.py, the 0.26
# threshold, app/predictor.py, the production models, or paper/report
# content. Pure read of final_features.csv + a fresh, separate model run.
#
# Run: python src/model/embedding_pooling_experiment.py
# =============================================================================

import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)

import ml_bridge  # noqa: E402

FINAL_CSV = os.path.join(PROJECT_ROOT, "dataset", "processed", "final_features.csv")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results", "experiments")
OUT_JSON = os.path.join(RESULTS_DIR, "embedding_pooling_experiment.json")

SAMPLE_SIZE = 500
RANDOM_STATE = 42
BATCH_SIZE = 16
N_ESTIMATORS = 100
BASELINE_F1 = 0.5391
BASELINE_AUC = 0.6346

# What counts as a "meaningful" reduction in anisotropy, decided BEFORE
# looking at the Part 2 result: mean pairwise cosine similarity dropping by
# at least 0.03 absolute (e.g. 0.9833 -> <=0.9533). Chosen because it is well
# outside sampling noise for n=500 (~124,750 pairs) and would represent a
# real, not cosmetic, geometry change -- not an after-the-fact justification.
MEANINGFUL_DROP_THRESHOLD = 0.03

METADATA_COLS = ["sample_id", "target", "project", "commit_id", "func"]
MET_COL_NAMES = [
    "loc", "function_count", "loop_count", "if_count", "return_count",
    "avg_line_length", "max_line_length", "comment_count",
    "total_lines", "blank_lines", "nesting_depth", "operator_count", "pointer_count",
]


def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def mean_pairwise_cosine_similarity(embeddings: np.ndarray) -> float:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normed = embeddings / np.clip(norms, 1e-12, None)
    sim = normed @ normed.T
    n = sim.shape[0]
    iu = np.triu_indices(n, k=1)
    return float(sim[iu].mean())


def embed_batch_cls_and_meanpool(tokenizer, model, codes):
    inputs = tokenizer(
        codes,
        return_tensors="pt",
        max_length=512,
        truncation=True,
        padding=True,
    )
    with torch.no_grad():
        output = model(**inputs)
    hidden = output.last_hidden_state  # (batch, seq_len, 768)
    mask = inputs["attention_mask"]  # (batch, seq_len)

    cls = hidden[:, 0, :].cpu().numpy()

    mask_f = mask.unsqueeze(-1).float()
    summed = (hidden * mask_f).sum(dim=1)
    counts = mask_f.sum(dim=1).clamp(min=1e-9)
    meanpooled = (summed / counts).cpu().numpy()

    return cls, meanpooled


def compute_embeddings(tokenizer, model, codes, batch_size=BATCH_SIZE):
    cls_all, mp_all = [], []
    for start in range(0, len(codes), batch_size):
        chunk = codes[start:start + batch_size]
        cls, mp = embed_batch_cls_and_meanpool(tokenizer, model, chunk)
        cls_all.append(cls)
        mp_all.append(mp)
    return np.vstack(cls_all), np.vstack(mp_all)


def main():
    t_start = time.time()
    result = {}

    section("LOAD final_features.csv (current, alignment-corrected dataset)")
    df = pd.read_csv(FINAL_CSV, encoding="utf-8")
    print(f"  Rows   : {len(df)}")
    print(f"  Columns: {len(df.columns)}")

    section(f"SAMPLE {SAMPLE_SIZE} RANDOM FUNCTIONS (random_state={RANDOM_STATE})")
    sample = df.sample(n=SAMPLE_SIZE, random_state=RANDOM_STATE).reset_index(drop=True)
    codes = sample["func"].astype(str).tolist()
    n_empty = sum(1 for c in codes if not c.strip())
    print(f"  Sampled {len(codes)} functions, {n_empty} empty/blank (should be 0).")

    section("LOAD REAL PRODUCTION TOKENIZER + MODEL (ml_bridge.get_codebert(), same path app/predictor.py uses)")
    tokenizer, model = ml_bridge.get_codebert()
    print(f"  Loaded: {type(model).__name__}")
    print(f"  CUDA available: {torch.cuda.is_available()}")

    section("PART 1+2: FRESH FORWARD PASS -- [CLS] and mean-pooled embeddings from the SAME hidden states")
    t0 = time.time()
    cls_emb, mp_emb = compute_embeddings(tokenizer, model, codes)
    print(f"  cls_emb shape: {cls_emb.shape}, mp_emb shape: {mp_emb.shape}")
    print(f"  Forward-pass time for {len(codes)} functions: {time.time() - t0:.1f}s")

    cls_sim = mean_pairwise_cosine_similarity(cls_emb)
    mp_sim = mean_pairwise_cosine_similarity(mp_emb)

    print(f"\n  [CLS] mean pairwise cosine similarity        : {cls_sim:.4f}")
    print(f"  Previously reported figure                    : 0.9833")
    print(f"  Difference from previously reported figure     : {cls_sim - 0.9833:+.4f}")
    print(f"\n  Mean-pooled mean pairwise cosine similarity   : {mp_sim:.4f}")

    drop = cls_sim - mp_sim
    meaningful = drop >= MEANINGFUL_DROP_THRESHOLD
    print(f"\n  Reduction (CLS - mean-pooled)                 : {drop:+.4f}")
    print(f"  Meaningful-reduction threshold                 : {MEANINGFUL_DROP_THRESHOLD}")
    print(f"  VERDICT: {'MEANINGFUL reduction' if meaningful else 'NOT a meaningful reduction'}")

    result["part1_reverify_cls_anisotropy"] = {
        "sample_size": SAMPLE_SIZE,
        "random_state": RANDOM_STATE,
        "cls_mean_pairwise_cosine_similarity": round(cls_sim, 4),
        "previously_reported_figure": 0.9833,
        "difference": round(cls_sim - 0.9833, 4),
    }
    result["part2_meanpool_comparison"] = {
        "meanpool_mean_pairwise_cosine_similarity": round(mp_sim, 4),
        "reduction_vs_cls": round(drop, 4),
        "meaningful_drop_threshold": MEANINGFUL_DROP_THRESHOLD,
        "meaningful": bool(meaningful),
    }

    if not meaningful:
        section("PART 3: SKIPPED")
        print("  Mean-pooling does not meaningfully reduce anisotropy on this sample --")
        print("  per instruction, not retraining. Reporting this finding as final.")
        result["part3_retrain"] = {"ran": False, "reason": "mean-pooling did not meaningfully reduce anisotropy"}
    else:
        section("PART 3: MEAN-POOLING SHOWS A MEANINGFUL REDUCTION -- RETRAINING ON FULL DATASET")
        codes_all = df["func"].astype(str).tolist()
        print(f"  Computing mean-pooled embeddings for all {len(codes_all)} rows "
              f"(this is the expensive part)...")
        t1 = time.time()
        _, mp_all = compute_embeddings(tokenizer, model, codes_all)
        print(f"  Done in {time.time() - t1:.1f}s")

        emb_cols = [f"embed_{i}" for i in range(768)]
        mp_df = pd.DataFrame(mp_all, columns=emb_cols)
        ast_cols = [c for c in df.columns if c.startswith("n_") or c == "max_depth"]
        met_cols = [c for c in df.columns if c in MET_COL_NAMES]
        assert len(ast_cols) == 11 and len(met_cols) == 13

        from sklearn.model_selection import train_test_split
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
        )
        from xgboost import XGBClassifier

        y = df["target"].values
        X = pd.concat([df[ast_cols + met_cols].reset_index(drop=True), mp_df], axis=1).values
        if np.isnan(X).sum() > 0:
            X = np.nan_to_num(X, nan=0.0)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE,
        )
        n_safe, n_vuln = int((y_train == 0).sum()), int((y_train == 1).sum())
        scale_pos_weight = round(n_safe / max(n_vuln, 1), 2)

        clf = XGBClassifier(
            n_estimators=N_ESTIMATORS, max_depth=6, learning_rate=0.1,
            scale_pos_weight=scale_pos_weight, random_state=RANDOM_STATE, verbosity=0,
        )
        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)
        y_proba = clf.predict_proba(X_test)[:, 1]

        f1 = float(f1_score(y_test, y_pred, zero_division=0))
        auc = float(roc_auc_score(y_test, y_proba))
        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1": f1,
            "auc": auc,
        }
        print(f"  Mean-pooled fusion  F1={f1:.4f}  AUC={auc:.4f}")
        print(f"  Production baseline F1={BASELINE_F1:.4f}  AUC={BASELINE_AUC:.4f}")
        print(f"  Difference           F1={f1 - BASELINE_F1:+.4f}  AUC={auc - BASELINE_AUC:+.4f}")

        result["part3_retrain"] = {
            "ran": True,
            "n_rows": int(len(df)),
            "metrics": metrics,
            "baseline_f1": BASELINE_F1,
            "baseline_auc": BASELINE_AUC,
            "f1_difference": round(f1 - BASELINE_F1, 4),
            "auc_difference": round(auc - BASELINE_AUC, 4),
        }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\n  Results saved: {OUT_JSON}")
    print(f"  Total runtime: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
