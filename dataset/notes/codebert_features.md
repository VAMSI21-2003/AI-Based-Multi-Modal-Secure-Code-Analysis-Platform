# CodeBERT Feature Extraction — Reference Document
**Project:** Multi-Modal Code Vulnerability Detection Using CodeBERT
**Day:** 7 — CodeBERT Embedding Extraction
**Script:** src/codebert/extract_embeddings.py

---

## Part 1: The Foundation — What is BERT?

### The Problem BERT Solved

Before 2018, AI models read text LEFT TO RIGHT — one word at a time,
just like reading a book. This is a problem because the meaning of a
word often depends on words that come LATER:

> "I went to the **bank** to deposit money."    (financial institution)
> "I sat on the river **bank** to fish."        (land beside a river)

A left-to-right model reads "bank" before seeing "deposit money" or
"to fish", so it cannot know which meaning to use.

### What BERT Does Differently

BERT (Bidirectional Encoder Representations from Transformers) was
released by Google in 2018. It reads the ENTIRE sentence simultaneously,
paying attention to all words in both directions at once.

The key mechanism is called **Self-Attention**:
- Every word "looks at" every other word and decides how relevant they are
- "bank" looks at "deposit" and "money" → high attention to both
- "bank" also looks at "river" and "fish" → would shift meaning entirely

This bidirectional understanding is why BERT produces much richer
representations than previous models.

### BERT's Architecture — The Transformer

BERT is built from "Transformer" blocks stacked on top of each other.
The base version has:
- **12 Transformer layers** (attention + processing at each layer)
- **12 attention heads** per layer (12 different "views" of each word)
- **768 hidden dimensions** (the internal representation width)
- **125 million parameters** (numbers the model learned during training)

The output of BERT is 768 numbers for EACH input token, representing
that token's meaning in the context of the entire sequence.

---

## Part 2: What is CodeBERT?

### From Natural Language to Source Code

BERT was trained on English Wikipedia and books — it understands
English text very well but knows nothing about programming languages.

CodeBERT (released by Microsoft Research in 2020) takes the BERT
architecture and retrains it on a mixture of:

| Training Data | Amount |
|---|---|
| Natural language text | Used for pre-warming |
| Code-comment pairs from GitHub | 8.35 million pairs |
| Source code only (no comments) | 3.86 million code files |

**Languages CodeBERT understands:**
Python, Java, JavaScript, PHP, Ruby, Go, and C/C++ (in later versions)

### How CodeBERT Differs from BERT

| Property | BERT | CodeBERT |
|---|---|---|
| Training data | English Wikipedia + books | GitHub code + comments |
| Vocabulary | English words and subwords | Code tokens + identifiers |
| Understands | English grammar, semantics | Programming constructs |
| Knows about | "the", "bank", "money" | `malloc`, `->`, `for`, `NULL` |
| Best for | Sentiment, summarisation, QA | Code search, bug detection, docstring generation |

### What CodeBERT Understands About Code

CodeBERT has processed millions of lines of real code, so it has
learned patterns such as:
- `malloc(size)` followed by using without checking return value = risky
- `free(ptr)` followed by `ptr->field` = use-after-free pattern
- `for (i=0; i<n; i++) { buf[i] = ... }` = loop over buffer
- Missing `if (size > MAX)` before buffer writes = missing bounds check

These patterns are encoded in its 125 million parameters. When you
feed a new C function, CodeBERT recognises which learned patterns the
code matches and encodes that recognition into the embedding vector.

---

## Part 3: What is an Embedding?

### The Word as a Location in Space

Imagine a 2D map. You can place related cities close together:
- New York and Boston are close (both US east coast)
- London and Paris are close (both Western Europe)
- Tokyo and Sydney are far from both groups

Now imagine doing this in 768-DIMENSIONAL space, with code functions
instead of cities. Two functions that do similar things get placed
close together; functions that do different things are far apart.

An **embedding** is the set of 768 coordinates that tells you WHERE
in this 768-dimensional space a particular function is located.

### What 768 Numbers Represent

The 768 numbers in a CodeBERT embedding are NOT individually
interpretable — you cannot say "dimension 142 measures pointer safety"
or "dimension 500 measures loop count". They are distributed
representations: each concept is spread across many dimensions, and
each dimension participates in many concepts.

What we CAN say is:
- Two functions with similar embeddings → CodeBERT thinks they are
  semantically similar
- Vulnerable functions tend to cluster together in the 768-D space
- Non-vulnerable functions tend to cluster in a different region

The classifier (trained in Day 9) learns to draw a boundary between
these clusters.

### Concrete Example from Our Script

The vulnerable and safe versions of our demo function produced:

```
Vulnerable:     [-0.0854, -0.0612, -0.2111, 0.1892, 0.1962, ..., 0.3778]
Non-Vulnerable: [-0.1108, -0.0759, -0.2227, 0.1741, 0.1694, ..., 0.3936]
Cosine similarity: 0.9996
```

**Cosine similarity of 0.9996** means they are placed almost at the
SAME location in 768-D space. The single added bounds check
(`|| src_size > sizeof(buf)`) barely changes CodeBERT's representation.

This is the most important finding of Day 7:

> CodeBERT ALONE cannot reliably distinguish the vulnerable version
> from the safe version of nearly identical code.
>
> This is EXACTLY WHY our project uses a MULTI-MODAL approach.
> AST features (Day 5) and Software Metrics (Day 6) capture the
> structural difference (one extra binary expression) that CodeBERT
> misses. Together, the three modalities cover what none can alone.

---

## Part 4: The [CLS] Token — How We Get One Vector Per Function

### The Problem: Variable-Length Code

Different C functions have different lengths:
- A short utility function: 5 lines, ~30 tokens
- A complex parser: 200 lines, ~2000 tokens

The classifier needs a FIXED-SIZE input. We cannot feed variable-length
sequences directly.

### The Solution: [CLS] Token

When CodeBERT processes input, it prepends a special token `[CLS]`
(CLaSsification) to the beginning:

```
Input tokens: [CLS] static int decode ( uint8_t * src ... ) [SEP]
Positions:      0      1      2     3    4      5   6  7   ...  512
```

The model is trained so that the [CLS] position's output vector
summarises the ENTIRE input sequence. After processing, we extract
just position 0 (the [CLS] output) as our 768-number function embedding.

```
CodeBERT output: (1 function × 512 positions × 768 dims)
                      ↓
Take position 0:  (1 function × 768 dims)
                      ↓
Squeeze:          768 numbers  ← THIS is the embedding we save
```

### Visualising the Process

```
C Function Text
"static int hq_decode(AVCodecContext *avctx, ...)"
         |
         v
   TOKENIZER
         |
         v
[CLS] [static] [int] [hq] [_] [decode] [(] [AV] ... [SEP] [PAD]...
  0      1      2     3   4     5       6    7   ...  last   512
         |
         v
   CODEBERT MODEL (12 layers of attention + transformation)
         |
         v
768 numbers per token position
         |
         v
Take position 0 (the [CLS] token output):
[ 0.1823, -0.4521, 0.0034, 0.7821, -0.2341, ..., 0.5671 ]
                        768 numbers
                             |
                             v
                    THE EMBEDDING VECTOR
                  Represents the whole function
```

---

## Part 5: Tokenization — How Code Becomes Numbers

### Step-by-Step Tokenization of C Code

Input code: `uint8_t buf[1024];`

**Stage 1 — Byte Pair Encoding (BPE) splits into sub-tokens:**
```
["uint", "8", "_", "t", " buf", "[", "1024", "]", ";"]
```
Note: BPE splits unknown words into known sub-parts. `uint8_t` becomes
`uint` + `8` + `_` + `t` because those parts appeared in training data.

**Stage 2 — Each sub-token gets a unique integer ID:**
```
[16791, 290, 62, 83, 29645, 58, 14196, 60, 26]
```
These IDs come from CodeBERT's vocabulary of 50,265 tokens.

**Stage 3 — Add special tokens and pad to 512:**
```
[0, 16791, 290, 62, 83, 29645, 58, 14196, 60, 26, 2, 1, 1, 1, ...]
 ^                                                   ^  ^^^
[CLS]=0                                           [SEP]=2  [PAD]=1
```

**Stage 4 — Attention mask (1=real token, 0=padding):**
```
[1,     1,     1,  ..., 1,        1,    0,  0,  0, ...]
[CLS]  real   real     real     [SEP]  PAD PAD  PAD
```

The attention mask tells CodeBERT to IGNORE the padding tokens when
computing attention.

---

## Part 6: Output Files

| File | Location | Description |
|---|---|---|
| `codebert_embeddings.npy` | `dataset/processed/` | NumPy array shape (N, 768) — fast to load |
| `codebert_embeddings.csv` | `dataset/processed/` | Full CSV with embed_000 to embed_767 columns |
| `codebert_metadata.csv` | `dataset/processed/` | target, project, commit_id — links rows to samples |

### Loading the embeddings later (Day 8):

```python
import numpy as np
import pandas as pd

# Load embeddings (fast — binary format)
embeddings = np.load("dataset/processed/codebert_embeddings.npy")
# Shape: (n_samples, 768)

# Load metadata (to get labels)
metadata = pd.read_csv("dataset/processed/codebert_metadata.csv")
# Columns: target, project, commit_id, embedding_row

labels = metadata["target"].values   # 0 or 1
```

### CSV Column Structure

| Column | Type | Description |
|---|---|---|
| `target` | int | Label: 1=vulnerable, 0=safe |
| `project` | string | FFmpeg or qemu |
| `commit_id` | string | Git commit reference |
| `embed_000` | float | Embedding dimension 0 |
| `embed_001` | float | Embedding dimension 1 |
| ... | float | ... |
| `embed_767` | float | Embedding dimension 767 |

---

## Part 7: How CodeBERT Fits in the Multi-Modal Architecture

```
C Function Source Code
        |
        +-----------> CodeBERT Branch (Today, Day 7)
        |              Input  : C code string (up to 512 tokens)
        |              Output : 768-dimensional embedding vector
        |              Captures: Semantic meaning of the code
        |
        +-----------> AST Branch (Day 5)
        |              Input  : C code string
        |              Output : 11 structural feature numbers
        |              Captures: Tree structure (loops, nesting, pointers)
        |
        +-----------> Metrics Branch (Day 6)
                       Input  : C code string
                       Output : 13 numeric features
                       Captures: Size, complexity, documentation quality

All three outputs  -->  Concatenated (768 + 11 + 13 = 792 features)
                   -->  Classifier
                   -->  Vulnerable / Non-Vulnerable
```

### Why Each Branch Is Needed

Our demo proved that the vulnerable and safe versions of nearly
identical code have cosine similarity 0.9996 in CodeBERT space.
No matter how good the classifier is, it cannot distinguish two
vectors that are 99.96% identical.

But in AST feature space, those same two functions differ in
`n_binary_ops` (5 vs 7) and `max_depth` (9 vs 10). In metric space,
they differ in `comment_count` (2 vs 3) and `operator_count` (3 vs 4).

Only by COMBINING all three representations does the classifier have
enough distinguishing signal.

---

## Part 8: Advantages of CodeBERT for Vulnerability Detection

| Advantage | Explanation |
|---|---|
| Pretrained on real code | Has already seen millions of functions — knows common patterns |
| Bidirectional context | Understands how each token relates to all others in the function |
| Semantic understanding | Knows that `malloc` + no null check is semantically risky |
| Language-aware | Understands C-specific constructs like pointers, casts, `sizeof` |
| Fixed-size output | Always produces 768 numbers regardless of function length |
| Transfer learning | Learning from 125M parameters costs less than training from scratch |
| Benchmark performance | State-of-the-art on CodeXGLUE defect detection benchmark |

---

## Part 9: Limitations of CodeBERT for Vulnerability Detection

| Limitation | Explanation |
|---|---|
| 512-token limit | Functions longer than ~2000 characters get truncated — end of function may be lost |
| High similarity problem | Near-identical vulnerable/safe pairs (our demo: 0.9996) are very hard to separate |
| No memory | Cannot reason across multiple function calls (inter-procedural analysis) |
| Black box | Cannot explain WHY it classifies something as vulnerable |
| Slow on CPU | Seconds per function on CPU — full dataset needs GPU or hours of waiting |
| Large download | 500 MB model file on first run |
| C-code bias | Trained mostly on high-level languages — C pointer semantics may be underrepresented |
| Static analysis blind spots | Misses runtime-dependent vulnerabilities like race conditions or environment variables |

---

## Part 10: Viva Questions and Answers

---

**Q1. What is CodeBERT and how does it differ from standard BERT?**

> CodeBERT is a pretrained transformer model released by Microsoft
> Research in 2020. It is built on the same architecture as BERT but
> was trained on 8.35 million code-comment pairs from GitHub across
> six programming languages: Python, Java, JavaScript, PHP, Ruby, and
> Go. While BERT was trained on English text and understands natural
> language semantics, CodeBERT was trained on source code and
> understands programming constructs such as function calls, pointer
> operations, loop structures, and variable declarations. CodeBERT
> can therefore produce meaningful representations of source code
> that capture the code's semantic intent rather than just its
> surface text patterns.

---

**Q2. What is an embedding and why do we use it?**

> An embedding is a fixed-size list of floating-point numbers that
> represents the meaning of a piece of input — in our case, a C
> function. CodeBERT produces 768 numbers for each function regardless
> of how long the function is. These 768 numbers act as a coordinate
> in a 768-dimensional space, where functions with similar behaviour
> are placed near each other. We use embeddings because machine
> learning classifiers require fixed-size numerical inputs — they
> cannot directly process variable-length code strings. The embeddings
> summarise the semantic content of the code in a form the classifier
> can work with.

---

**Q3. What is the [CLS] token and why do we use it for embeddings?**

> The [CLS] token is a special token prepended to every input sequence
> before it is processed by BERT or CodeBERT. The transformer model is
> trained so that the output at the [CLS] position aggregates
> information from the entire input sequence and represents a summary
> of the whole input. When we want a single embedding vector for an
> entire C function, we take the [CLS] output vector — the 768 numbers
> at position 0 in the model's output — as the function's embedding.
> This approach is standard practice for classification tasks using
> BERT-based models.

---

**Q4. What does torch.no_grad() do and why is it used?**

> During model training, PyTorch tracks every mathematical operation
> in order to compute gradients — the values that tell the optimizer
> how to adjust the model's parameters to improve performance. This
> tracking consumes significant memory and computation time. During
> inference (when we are extracting embeddings, not training the
> model), we do not need to update any parameters — we are only doing
> a forward pass to read the output. Using torch.no_grad() as a
> context manager disables gradient tracking for all operations inside
> the block, which reduces memory usage by approximately 50% and
> speeds up computation. It is required best practice whenever using
> a pretrained model for prediction or feature extraction.

---

**Q5. What does cosine similarity of 0.9996 between the vulnerable and safe samples mean, and why is it important?**

> Cosine similarity measures how similar two vectors are in direction
> in high-dimensional space, ranging from 0 (completely different) to
> 1 (identical). A cosine similarity of 0.9996 between the vulnerable
> and safe function embeddings means CodeBERT placed them at nearly
> the same location in its 768-dimensional embedding space. The single
> added bounds check in the safe version is a tiny textual change that
> CodeBERT does not significantly distinguish. This finding directly
> motivates our multi-modal approach: CodeBERT alone cannot reliably
> separate nearly identical vulnerable and safe code pairs. By
> combining CodeBERT embeddings with AST structural features (which
> show the extra binary expression from the bounds check) and software
> metrics (which show the extra operator), the combined representation
> provides distinguishing signal that no single modality captures alone.

---

**Q6. Why is there a 512-token limit and how do we handle functions longer than this?**

> The 512-token limit is an architectural constraint of the original
> BERT model and all models derived from it, including CodeBERT. The
> self-attention mechanism computes relationships between every pair
> of tokens, and the memory requirement grows quadratically with
> sequence length — doubling the tokens requires four times the memory.
> The original authors chose 512 as a practical balance. In our script,
> we handle this with truncation: if a C function exceeds 512 tokens,
> the tokenizer keeps the first 512 tokens and discards the rest.
> This means the end of very long functions may be lost. For the
> Devign dataset, the average function is approximately 200-300 tokens,
> so most functions fit within the 512-token limit without truncation.
> For a future improvement, techniques like sliding window attention
> or hierarchical encoding could handle longer functions.

---

**Q7. What is the difference between the .npy and .csv output files?**

> The .npy file is a NumPy binary format file that stores the raw
> floating-point numbers in binary form without any text conversion.
> It is compact (roughly one quarter the size of an equivalent CSV),
> fast to load (no parsing required), and maintains full floating-point
> precision. The .csv file stores the same numbers as human-readable
> text with commas between values. It is larger and slower to load but
> can be opened in Excel, inspected manually, and loaded by any tool
> that reads CSV files. In the machine learning pipeline, we load the
> .npy file for efficiency. The .csv is provided for transparency and
> manual inspection.

---

## Part 11: How to Run the Script

```powershell
# Step 1: Open VS Code terminal
# Step 2: Activate venv
.\venv\Scripts\activate

# Step 3: Install packages (if not already installed)
pip install transformers torch

# Step 4: Navigate to script
cd src\codebert

# Step 5: Run (demo mode — first 200 samples, no dataset required)
python extract_embeddings.py
```

**To process ALL samples (recommended on Google Colab with GPU):**

Open `extract_embeddings.py` and change line:
```python
MAX_SAMPLES = 200   # change this
```
to:
```python
MAX_SAMPLES = None  # process everything
```

**Google Colab Setup (for GPU processing):**
1. Go to colab.research.google.com
2. Runtime → Change runtime type → T4 GPU
3. Upload your project folder (or clone from GitHub)
4. Run the script — full dataset takes ~15-30 minutes on GPU

---

## Part 12: Key Insight for the Viva

The most important finding from Day 7 is the **cosine similarity of 0.9996** between the vulnerable and safe versions of our demo function. This single number justifies the entire multi-modal architecture of our project.

If CodeBERT alone could distinguish them, we would not need AST features or software metrics. The fact that it CANNOT — even with 125 million parameters and pre-training on millions of code files — demonstrates that this is a genuinely hard problem, and that combining multiple analysis modalities is not just an academic exercise but a practical necessity.

This is the finding you should confidently present in your viva when explaining why the project uses three branches instead of just CodeBERT alone.

---
*Document prepared on Day 7 — CodeBERT Embedding Extraction*
