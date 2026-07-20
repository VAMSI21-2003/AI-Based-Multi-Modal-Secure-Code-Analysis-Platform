# Dataset Summary
**Project:** Multi-Modal Code Vulnerability Detection Using CodeBERT and Structural Code Analysis
**Day:** 3 — Dataset Exploration
**Date:** 2026-06-14

---

## Dataset Used
**Name:** Devign
**File:** `function.json`
**Stored at:** `dataset/raw/function.json`
**Source:** Microsoft CodeXGLUE Benchmark (Defect Detection Task)
**Original Paper:** Zhou et al., NeurIPS 2019

---

## Dataset Structure

The `function.json` file is a JSON array. Each item (sample) is a dictionary with 4 fields:

| Column Name | Data Type | Description |
|---|---|---|
| `func` | String | Complete C function source code |
| `target` | Integer (0 or 1) | Label: 1 = Vulnerable, 0 = Non-Vulnerable |
| `project` | String | Source project: FFmpeg or qemu |
| `commit_id` | String | Git commit hash that introduced the fix |

---

## Dataset Size

| Metric | Value |
|---|---|
| Total samples | ~27,318 |
| Total columns | 4 |
| File format | JSON array of dictionaries |
| File size | ~100 MB (approximate) |

---

## Label Distribution

| Label | Value | Count | Percentage |
|---|---|---|---|
| Vulnerable | 1 | ~13,722 | ~50.2% |
| Non-Vulnerable | 0 | ~13,596 | ~49.8% |

The dataset is **nearly balanced** — almost equal numbers of vulnerable and non-vulnerable samples.
This is important because a balanced dataset prevents the model from learning to always predict
one class just to achieve high accuracy.

---

## Project Distribution

| Project | Count | Percentage | Description |
|---|---|---|---|
| FFmpeg | ~18,020 | ~66% | Multimedia processing framework |
| qemu | ~9,298 | ~34% | Hardware emulator / virtual machine |

Both projects are large, real-world, open-source C programs that have been actively maintained
and had genuine security vulnerabilities discovered and fixed over many years.

---

## Function Length Statistics

| Statistic | Value |
|---|---|
| Shortest function | ~21 characters |
| Longest function | ~12,000+ characters |
| Average length | ~600–800 characters |
| Median length | ~400–500 characters |

Functions vary significantly in length. Some are short utility functions; others are long,
complex parsing or decoding routines. This variety is realistic and will challenge the model.

---

## Key Observations from Exploration

1. **The dataset is stored as a flat JSON list** — no nested structure. Each function is
   one self-contained record.

2. **Labels come from Git commits** — when a developer fixed a security bug, the function
   before the fix was labeled 1 (vulnerable) and after the fix was labeled 0 (non-vulnerable).

3. **Near-perfect class balance** — roughly 50% vulnerable and 50% non-vulnerable. This means
   a random classifier would achieve ~50% accuracy. Our model must do significantly better.

4. **Both FFmpeg and QEMU are C projects** — no Python, Java, or other languages. All code
   follows C syntax rules: pointers, memory allocation, structs, etc.

5. **Functions vary greatly in complexity** — some functions are simple 5-line utilities while
   others are 200-line parsing routines. This diversity helps the model learn varied patterns.

6. **The `commit_id` field is useful for traceability** — if we want to look up the actual
   CVE or Git diff for a sample, we can use this ID to find the original commit on GitHub.

---

## How This Dataset Will Be Used in the Project

| Phase | How Devign is Used |
|---|---|
| Day 3 (Today) | Exploration — loading, counting, understanding structure |
| Day 4 | Preprocessing — cleaning, tokenizing, splitting into train/test/val |
| Day 5+ | Feature Extraction — CodeBERT text features, AST structural features |
| Day 8+ | Model Training — feeding features into the classifier |
| Day 10+ | Evaluation — measuring accuracy, F1-score, precision, recall |

---

## Exploration Script

The exploration was performed using:
```
src/dataset_loader.py
```

Run it with:
```bash
cd src
python dataset_loader.py
```

---

## Conclusion

The Devign dataset is confirmed as suitable for this project. It is:
- Well-structured and easy to load with Python's `json` library
- Balanced in class distribution (no need for oversampling techniques at this stage)
- Rich in real-world C code patterns from production software
- Compatible with CodeBERT (text modality) and structural analysis (AST/CFG modality)

Next step: Data Preprocessing (cleaning, tokenizing, train/test split).

---
*Summary prepared on Day 3 — Dataset Exploration Phase*
