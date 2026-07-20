# =============================================================================
# precompute_pca.py
# One-time offline script: fits a 2D PCA on the EXISTING CodeBERT embeddings
# (dataset/processed/codebert_embeddings.npy) purely for visualisation --
# lets the UI plot "where does this new function land relative to the
# training set" on a 2D scatter. Does NOT touch or retrain the classifier.
#
# Run once:  python backend/precompute_pca.py
# Outputs:
#   backend/data/pca_model.npz         (mean vector + 2 principal components)
#   backend/data/pca_background.json   (sampled 2D points + labels for the
#                                        scatter background layer)
# =============================================================================

import os
import json
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "dataset", "processed")
OUT_DIR = os.path.join(PROJECT_ROOT, "backend", "data")
os.makedirs(OUT_DIR, exist_ok=True)

EMB_PATH = os.path.join(PROCESSED_DIR, "codebert_embeddings.npy")
META_PATH = os.path.join(PROCESSED_DIR, "codebert_metadata.csv")

SAMPLE_SIZE = 2500
RANDOM_STATE = 42


def main():
    print("Loading embeddings...")
    embeddings = np.load(EMB_PATH)
    meta = pd.read_csv(META_PATH)
    n = embeddings.shape[0]
    print(f"  {n} embeddings of dim {embeddings.shape[1]}")

    print("Fitting PCA(2) on full embedding matrix (visualisation only)...")
    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    coords_full = pca.fit_transform(embeddings)
    print(f"  Explained variance ratio: {pca.explained_variance_ratio_}")

    np.savez(
        os.path.join(OUT_DIR, "pca_model.npz"),
        mean=pca.mean_.astype(np.float64),
        components=pca.components_.astype(np.float64),
        explained_variance_ratio=pca.explained_variance_ratio_.astype(np.float64),
    )

    rng = np.random.default_rng(RANDOM_STATE)
    idx = rng.choice(n, size=min(SAMPLE_SIZE, n), replace=False)

    background = {
        "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
        "points": [
            {
                "x": round(float(coords_full[i, 0]), 3),
                "y": round(float(coords_full[i, 1]), 3),
                "label": int(meta.iloc[i]["target"]) if "target" in meta.columns else None,
            }
            for i in idx
        ],
    }

    with open(os.path.join(OUT_DIR, "pca_background.json"), "w", encoding="utf-8") as f:
        json.dump(background, f)

    print(f"Saved: {os.path.join(OUT_DIR, 'pca_model.npz')}")
    print(f"Saved: {os.path.join(OUT_DIR, 'pca_background.json')} ({len(idx)} points)")


if __name__ == "__main__":
    main()
