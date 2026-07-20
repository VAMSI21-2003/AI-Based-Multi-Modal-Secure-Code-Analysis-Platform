# Dataset Research

## Selected Dataset
**Devign** — A function-level vulnerability dataset sourced from real-world open-source C projects
(FFmpeg and QEMU), introduced in the NeurIPS 2019 paper:
"Devign: Effective Vulnerability Identification by Learning Comprehensive Program Semantics via
Graph Neural Networks" by Zhou et al.

---

## Why This Dataset Was Chosen

1. **Publicly available** — freely downloadable, no license barriers for academic use.
2. **Real-world code** — samples come from production-grade open-source software (FFmpeg, QEMU),
   making the dataset representative of actual vulnerabilities developers encounter.
3. **Balanced labeling** — roughly equal number of vulnerable and non-vulnerable samples avoids
   severe class imbalance during training.
4. **Multi-modal friendly** — each sample is a complete C function, making it suitable for both
   text-based analysis (CodeBERT) and structural analysis (AST/CFG/PDG).
5. **Widely benchmarked** — used in dozens of published papers, so results can be directly
   compared against prior work.
6. **MCA project scope** — size (~27,000 samples) is large enough to train meaningful models but
   small enough to process on a personal machine with reasonable time.

---

## Programming Languages
- **C only**
- All samples are complete C functions extracted from FFmpeg (multimedia framework) and QEMU
  (hardware emulator).
- No multi-language mixing; this makes preprocessing consistent.

---

## Labels
Devign uses **binary labels**:

| Label | Value | Meaning |
|-------|-------|---------|
| Vulnerable | `1` | The function contains at least one security vulnerability |
| Non-Vulnerable | `0` | The function has no known vulnerability |

Labels were assigned by developers through the Git commit history: if a commit message indicated
a security fix, the function before the fix was labeled 1 (vulnerable) and after the fix was
labeled 0 (non-vulnerable).

---

## Advantages

1. **Real code, real bugs** — not synthetic; vulnerabilities were found and fixed by actual
   developers in production software.
2. **Function-level granularity** — each sample is one complete function, which is the natural
   unit for both manual review and automated analysis.
3. **Commit-history provenance** — labels are derived from security-fix commits, giving a clear
   audit trail.
4. **Benchmark status** — accepted as a standard benchmark in the vulnerability detection
   research community, enabling direct comparison.
5. **Sufficient size** — ~27,318 samples provide enough data to train deep learning models
   without severe overfitting.
6. **Structural richness** — function-level C code naturally contains control flow, data flow,
   and call structures useful for structural analysis.
7. **Compatible with CodeBERT** — code text can be directly tokenized and fed into CodeBERT
   after minimal preprocessing.

---

## Limitations

1. **C-only** — does not cover Python, Java, or other modern languages; findings may not
   generalize across languages.
2. **Binary labels only** — does not specify the vulnerability type (e.g., buffer overflow vs.
   null pointer dereference); fine-grained classification requires additional annotation.
3. **Domain-specific** — both source projects (FFmpeg, QEMU) are systems-level multimedia/VM
   software; vulnerabilities in web or embedded domains may differ structurally.
4. **Label noise** — commit messages are written by humans; some security fixes may be mislabeled
   or missed.
5. **No CWE mapping** — unlike NVD-based datasets, Devign does not provide CWE (Common Weakness
   Enumeration) identifiers per sample.
6. **Imbalance possible** — while roughly balanced, the ratio is not perfectly 50/50 and varies
   by reported version of the dataset.
7. **Outdated CVEs** — vulnerabilities fixed years ago may not represent modern attack patterns.

---

## Research Relevance

- Devign was introduced at **NeurIPS 2019**, one of the top-tier machine learning conferences,
  giving it strong academic credibility.
- It is used as the primary benchmark in papers on Graph Neural Networks (GNNs) for code,
  CodeBERT-based detectors, and multi-modal vulnerability detection systems.
- The dataset directly aligns with our project goal: combining **semantic features** (via
  CodeBERT) and **structural features** (via AST/CFG) for vulnerability detection.
- Several state-of-the-art methods (LineVul, ReVeal, IVDetect, VulBERTa) all evaluate on
  Devign, making it the standard choice for comparison.

---

## Dataset Comparison Summary

| Property | Devign | VulDeePecker | Draper VDISC |
|---|---|---|---|
| Size | ~27,318 samples | ~61,000 slices | ~1.27M samples |
| Language | C only | C/C++ | C/C++ |
| Granularity | Function-level | Slice-level | Function-level |
| Label Type | Binary (0/1) | Binary (0/1) | Binary (0/1) |
| Popularity | Very High | High | Moderate |
| Ease of Use | High | Medium | Medium |
| MCA Suitability | Excellent | Good | Poor (too large) |
| Multi-Modal Support | Excellent | Good | Good |

---

## Final Decision

**Selected Dataset: Devign**

Devign is selected as the primary dataset for this project for the following reasons:

- It is the most widely used benchmark in current vulnerability detection literature, ensuring
  our results are comparable and academically meaningful.
- Its function-level C code samples are well-suited for both CodeBERT (text modality) and AST
  / Control Flow Graph analysis (structural modality), directly supporting our multi-modal
  architecture.
- Its manageable size (~27K samples) allows full training and evaluation on a local machine
  without requiring cloud GPU resources.
- It is freely available, academically accepted, and has clear binary labels derived from
  real-world Git security commits, making it both reliable and reproducible.

**Download source (for reference):** The Devign dataset JSON file is available from the
original paper's GitHub repository and mirrored on research data platforms. The file is
named `function.json` and contains all samples with their labels.

---
*Notes prepared: Day 2 — Dataset Research Phase*
*Project: Multi-Modal Code Vulnerability Detection Using CodeBERT and Structural Code Analysis*
