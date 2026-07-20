# Feature Fusion — Reference Document
**Project:** Multi-Modal Code Vulnerability Detection Using CodeBERT
**Day:** 8 — Feature Fusion
**Script:** src/fusion/fuse_features.py

---

## Part 1: What is Feature Fusion?

### The Problem of Partial Views

In our project, three different scripts (Days 5, 6, 7) analysed the same
C function from three different angles. Each produced a separate file:

```
devign_ast_features.csv     (Day 5)  →  11 numbers per function
metrics_features.csv        (Day 6)  →  13 numbers per function
codebert_embeddings.csv     (Day 7)  →  768 numbers per function
```

These three files are NOT connected — they are separate tables. A classifier
cannot read three separate tables. It needs ONE table where every row
contains ALL information about one function.

**Feature fusion** is the process of COMBINING these three tables into one.

The result is saved in:
```
final_features.csv    →    792 numbers per function
                           (11 + 13 + 768 = 792)
```

---

## Part 2: The Analogy — Three Doctors

Imagine a patient is examined by three specialist doctors:

| Doctor | What they examine | Analogy in our project |
|---|---|---|
| Doctor A | X-ray scan | AST features (code structure) |
| Doctor B | Blood test | Software metrics (code statistics) |
| Doctor C | Symptoms interview | CodeBERT embedding (code semantics) |

Each doctor gives a PARTIAL picture:
- Doctor A alone may miss what blood tests show
- Doctor B alone may miss what the X-ray reveals
- Doctor C alone may miss structural problems

The DIAGNOSIS improves when all three reports are combined into one patient record.

Feature fusion = combining all three reports into one patient record.

---

## Part 3: The Three Feature Sources

### Source 1 — AST Features (Day 5)

**What it captures:** The STRUCTURAL SHAPE of the code

| Feature | What it counts | Vulnerability signal |
|---|---|---|
| n_loops | for + while + do-while loops | Loops without bounds checks → buffer overflow |
| n_if_statements | if / else-if blocks | Guard conditions protect against bad inputs |
| n_pointer_ops | pointer dereferences | High pointer ops → use-after-free risk |
| max_depth | deepest AST nesting | Deep nesting → complex, error-prone logic |
| n_binary_ops | arithmetic/comparison ops | Missing comparison → missing bounds check |
| n_returns | return statements | Many early returns → possible resource leak |
| n_function_calls | function call expressions | External calls with unchecked return values |
| n_assignments | assignment expressions | Unchecked assignments → type confusion |
| n_total_nodes | all AST nodes | Overall code complexity |
| n_error_nodes | unparseable nodes | Malformed code → unreliable features |
| n_functions | function definitions | Usually 1 per Devign sample |

**Total: 11 features**

### Source 2 — Software Metrics (Day 6)

**What it captures:** QUANTITATIVE PROPERTIES of the code text

| Feature | What it measures | Vulnerability signal |
|---|---|---|
| loc | Lines of Code (non-empty) | Large functions more likely to contain bugs |
| loop_count | Total loops | Loops without matching ifs → no bounds check |
| if_count | If statements | More ifs = more guard conditions |
| pointer_count | `->` and `*identifier` | High count = higher memory-safety risk |
| comment_count | `//` and `/* */` blocks | Fewer comments = less careful code |
| nesting_depth | Max brace depth | Deep nesting hides logic errors |
| operator_count | Arithmetic operators | Many *, << without bounds check = overflow risk |
| avg_line_length | Avg chars per line | Long lines = complex, hard-to-audit expressions |
| max_line_length | Longest single line | Very long lines are often skipped during review |
| function_count | Function definitions | Context: usually 1 per Devign sample |
| return_count | Return statements | Multiple returns = complex cleanup logic |
| total_lines | All lines | Overall size including blank lines |
| blank_lines | Empty-only lines | Blank line ratio = code readability |

**Total: 13 features**

### Source 3 — CodeBERT Embeddings (Day 7)

**What it captures:** The SEMANTIC MEANING of the code

CodeBERT (125 million parameters, trained on 8.35M code-comment pairs)
converts each function into 768 floating-point numbers. These numbers
encode the "fingerprint" of the code's meaning.

Two functions that do similar things produce similar 768-number vectors.
Two functions that do different things produce different vectors.

The 768 dimensions are NOT individually interpretable (dimension 142 does
not "mean" anything specific). The meaning is DISTRIBUTED across all 768
dimensions simultaneously.

**Total: 768 features**

---

## Part 4: The Feature Fusion Process

### Step-by-Step

**Step 1** — All three source files come from the SAME cleaned dataset
(`devign_cleaned.csv`) and were processed in the SAME ORDER. This means:
- Row 0 in the AST file = Row 0 in the Metrics file = Row 0 in CodeBERT
- They all refer to the SAME C function

**Step 2** — We add a `sample_id` column to each file = the row number
(0, 1, 2, ...). This is the KEY used to match rows across files.

**Step 3** — We perform two joins:
```
Merge 1:   AST features   + Metrics features   =  24-feature table
           (on sample_id, inner join)

Merge 2:   24-feature table + CodeBERT embeddings =  792-feature table
           (on sample_id, inner join)
```

**Step 4** — We validate the result and save to `final_features.csv`.

### Inner Join — What Does It Mean?

The `how="inner"` parameter means: keep ONLY rows where the `sample_id`
appears in BOTH tables being merged.

```
AST file:       sample_id = [0, 1, 2, 3, 4, ... , 26999]   (all samples)
Metrics file:   sample_id = [0, 1, 2, 3, 4, ... , 26999]   (all samples)
CodeBERT file:  sample_id = [0, 1, 2, 3, ... , 199]         (first 200 only)

After inner join:
final_features.csv:  sample_id = [0, 1, 2, 3, ... , 199]  (200 rows)
```

A sample present in two files but missing from the third is EXCLUDED.
This ensures no row has missing (NaN) features, which would crash the classifier.

---

## Part 5: The Final Feature Vector

After fusion, each C function in `final_features.csv` is represented by:

```
[  n_functions, n_loops, n_if_statements, n_assignments, n_returns,
   n_pointer_ops, n_function_calls, n_binary_ops, max_depth,
   n_total_nodes, n_error_nodes,
                                                                   ]  <- 11 AST
   loc, function_count, loop_count, if_count, return_count,
   avg_line_length, max_line_length, comment_count, total_lines,
   blank_lines, nesting_depth, operator_count, pointer_count,
                                                                      <- 13 Metrics
   embed_000, embed_001, embed_002, ..., embed_767                    <- 768 CodeBERT

   =  792 numbers total
```

This 792-dimensional vector is what the classifier (Day 9) will train on.

### The final_features.csv structure:

| Column position | Column name | Type | Description |
|---|---|---|---|
| 1 | sample_id | int | Row number in devign_cleaned.csv |
| 2 | target | int | 0=safe, 1=vulnerable |
| 3 | project | str | FFmpeg or qemu |
| 4 | commit_id | str | Git commit reference |
| 5-15 | n_functions ... n_error_nodes | int | 11 AST features |
| 16-28 | loc ... pointer_count | int/float | 13 metric features |
| 29-796 | embed_000 ... embed_767 | float | 768 CodeBERT dimensions |

**Total: 796 columns** (4 metadata + 792 features)

---

## Part 6: Types of Feature Fusion

Our project uses **Early Fusion** (also called **Feature-Level Fusion**).
There are three main types:

### Early Fusion (what we use)

All features from all branches are CONCATENATED into one long vector
BEFORE any classifier sees them.

```
AST(11) + Metrics(13) + CodeBERT(768)  →  [one vector of 792 numbers]
                                                       |
                                                  Classifier
                                                       |
                                              Vulnerable / Safe
```

**Advantages:**
- Simple to implement (one join operation)
- Classifier can learn CROSS-MODAL interactions
  (e.g., "high n_loops AND high embed_234" together = risky)
- All 792 features are optimised together

**Disadvantage:**
- High-dimensional input (792 features can slow training)
- CodeBERT's 768 dimensions dominate the feature space numerically

---

### Late Fusion (decision-level)

Each branch trains its OWN separate classifier. Their predictions are
combined at the end (usually by voting or averaging).

```
AST(11)       →  Classifier A  →  prediction A
Metrics(13)   →  Classifier B  →  prediction B   →  Vote  →  Final prediction
CodeBERT(768) →  Classifier C  →  prediction C
```

**When to use it:** When the branches are very different in type
(e.g., text + image + audio). More complex to train.

---

### Intermediate Fusion (feature-learning fusion)

Each branch is first processed by its own neural network to learn a
compressed representation. The compressed outputs are then concatenated
and fed to a final classifier.

```
AST(11)       →  Neural net A  →  64-dim vector
Metrics(13)   →  Neural net B  →  64-dim vector   →  [192-dim]  →  Classifier
CodeBERT(768) →  Neural net C  →  64-dim vector
```

**When to use it:** When branches have very different scales or types.
More powerful but requires deep learning framework.

**We use Early Fusion** because:
- It is standard in academic vulnerability detection research
- It is easy to understand and explain in a viva
- It works well when all features are already in numeric form

---

## Part 7: Advantages of Multi-Modal Fusion

| Advantage | Explanation |
|---|---|
| Complementary information | Each branch captures aspects the others miss |
| Robustness | If CodeBERT is uncertain, AST/metrics can still contribute |
| Empirically justified | Cosine similarity 0.9996 proves CodeBERT alone cannot separate near-identical functions |
| State-of-the-art design | Multi-modal approaches consistently outperform single-modal in vulnerability detection papers |
| Interpretability | AST and metric features are human-interpretable; we can explain why a function is flagged |

---

## Part 8: Limitations of Feature Fusion (Early Fusion)

| Limitation | Explanation |
|---|---|
| Curse of dimensionality | 792 features with only a few thousand training samples may cause overfitting |
| Feature scale mismatch | CodeBERT embeddings are in range [-3, +14]; LOC might be 200; classifier needs normalisation |
| No interaction learning | Concatenation assumes features are independent; a neural network would learn cross-feature patterns better |
| Missing data problem | Any sample missing from ONE file is excluded from the fused dataset |
| Redundancy | n_loops (AST) and loop_count (Metrics) measure the same thing differently — redundant |

---

## Part 9: Vulnerability Detection Relevance

### Why Multi-Modal is Necessary

Our Day 7 experiment proved that CodeBERT ALONE cannot detect the vulnerability
in our test case:

- Vulnerable function (missing bounds check): embedding vector = 768 numbers
- Safe function (bounds check added): embedding vector = 768 numbers
- Cosine similarity between the two: **0.9996**

A score of 0.9996 means CodeBERT places both functions at almost the SAME
location in 768-dimensional space. No classifier can distinguish two vectors
that are 99.96% identical.

However, in AST space:
- Vulnerable: `n_binary_ops = 5` (the bounds check is missing)
- Safe: `n_binary_ops = 7` (the `||` and `>` in the bounds check add 2 more)

And in metric space:
- Vulnerable: `operator_count = 3`
- Safe: `operator_count = 4` (the extra `||` adds one more operator)

The classifier WITH all 792 features can detect this structural difference
even when CodeBERT cannot.

### The Multi-Modal Signal Chain

```
Security vulnerability exists in code
             |
     Missing bounds check
     (one extra binary expression is absent)
             |
         Detected by:
         AST    -> n_binary_ops: 5 vs 7 (DIFFERS)
         Metrics -> operator_count: 3 vs 4 (DIFFERS)
         CodeBERT -> similarity: 0.9996 (CANNOT DISTINGUISH)
             |
     All three combined -> classifier sees the difference
             |
         Prediction: VULNERABLE (label = 1)
```

---

## Part 10: Viva Questions and Answers

---

**Q1. What is feature fusion and why is it needed in your project?**

> Feature fusion is the process of combining features from multiple
> different sources into one unified feature vector that a machine
> learning classifier can process. In our project, three scripts
> produce three separate CSV files: AST features (11 columns), software
> metrics (13 columns), and CodeBERT embeddings (768 columns). A
> classifier cannot read three separate tables — it needs one row of
> numbers per function. Feature fusion merges these three files into
> final_features.csv, where each row has 792 feature values for one
> C function (11 + 13 + 768 = 792). The Day 9 classifier then reads
> this file and learns to predict whether each function is vulnerable
> or safe.

---

**Q2. What is the difference between early fusion, late fusion, and intermediate fusion?**

> Early fusion (also called feature-level fusion) concatenates all
> features from all branches into one long vector before any
> classifier sees them. This is what our project uses.
>
> Late fusion (decision-level fusion) trains a separate classifier
> for each branch and combines their individual predictions at the
> end — for example by majority voting or averaging probabilities.
>
> Intermediate fusion has each branch processed by its own small
> neural network that learns a compressed representation, and then
> concatenates those compressed outputs before the final classifier.
>
> We chose early fusion because it is the simplest to implement,
> requires no separate classifiers per branch, and allows the
> classifier to learn interactions between features from different
> branches simultaneously.

---

**Q3. How do you align the three feature files when merging?**

> All three feature files were produced from the same cleaned dataset
> file (devign_cleaned.csv) in the same row order. This means row
> number 0 in the AST file corresponds to the same C function as
> row number 0 in the metrics file and row number 0 in the CodeBERT
> file. We exploit this by adding a `sample_id` column to each file
> equal to the row number (0, 1, 2, ...). For the CodeBERT file, the
> Day 7 script saved an `embedding_row` column that already stores
> this position. We then use pandas `merge()` with `how="inner"` on
> `sample_id` to join the three tables. The inner join keeps only
> rows where the sample_id appears in all three files, ensuring no
> row has missing features.

---

**Q4. What is a pandas merge and what does how="inner" mean?**

> `pd.merge(left, right, on="column", how="inner")` is a pandas
> function that joins two DataFrames row-by-row based on matching
> values in a specified column. For each value of `sample_id` in the
> left DataFrame, it finds the row with the same `sample_id` value
> in the right DataFrame and combines their columns side by side.
>
> The `how="inner"` parameter specifies an INNER JOIN, which means
> only rows whose `sample_id` value appears in BOTH DataFrames are
> kept in the result. If a `sample_id` exists in the left file but
> not in the right file, that row is DROPPED from the output. This
> prevents partial rows with NaN values, which would cause the
> classifier to crash. In our case, if CodeBERT only processed 200
> samples, the final fused table will have 200 rows (not the full
> 27,000), because those are the only samples with all three types
> of features available.

---

**Q5. Why do you use 792 features? Is more features always better?**

> We use 792 features because that is what our three branches produce:
> 11 AST features plus 13 software metrics plus 768 CodeBERT embedding
> dimensions. More features is NOT always better. There are two main
> risks from having many features:
>
> First, the curse of dimensionality: with 792 features but only a
> few thousand training samples, the model has too many parameters to
> learn and may overfit the training data (memorise it rather than
> generalise to new data).
>
> Second, feature scale mismatch: CodeBERT embedding values are in
> the range roughly -3 to +14, while LOC might be 200 and pointer_count
> might be 5. A classifier without normalisation would treat the larger
> numbers as more important, even if they are not. Feature normalisation
> (scaling all features to a common range, done in Day 9) addresses this.
>
> Despite these risks, our 792 features are well-motivated: each one
> captures a different aspect of the code that alone is insufficient
> but together provides strong predictive signal.

---

**Q6. What would happen if you used only CodeBERT embeddings and skipped AST and metrics?**

> We demonstrated in Day 7 that the cosine similarity between the
> CodeBERT embeddings of a vulnerable function and its safe version
> (differing only by one bounds check) was 0.9996. This means
> CodeBERT placed both functions at almost the same position in
> 768-dimensional space. A classifier trained only on CodeBERT
> embeddings would see two nearly identical input vectors for a
> vulnerable and a safe function and would have insufficient signal
> to distinguish them.
>
> The AST feature `n_binary_ops` differed by 2 between the same pair
> (5 vs 7), and the metric `operator_count` differed by 1 (3 vs 4).
> By adding these 24 additional features, we give the classifier a
> second and third view of the same functions that reveals the
> structural difference CodeBERT cannot see. This is why multi-modal
> fusion consistently outperforms single-modal approaches in
> vulnerability detection research.

---

**Q7. What validation checks does your fusion script perform and why?**

> The fusion script performs four validation checks after merging:
>
> Check 1 — Row count: Verifies the merged table has at least one row.
> Zero rows means the sample_id values did not match across the three
> files, indicating the scripts were run on different dataset versions.
>
> Check 2 — Missing values: Counts NaN cells in every feature column.
> NaN values crash most classifiers. If found, we fill them with zero
> (a conservative default that treats unknown features as absent).
>
> Check 3 — Duplicate sample IDs: Each sample_id should appear exactly
> once. Duplicates indicate the source file had repeated rows (usually
> caused by running a script twice and appending output). We keep only
> the first occurrence of each duplicate.
>
> Check 4 — Label integrity: Verifies the target column contains ONLY
> the values 0 (safe) and 1 (vulnerable). Any other value (NaN, -1,
> string) would cause the classifier to fail. We also print the class
> distribution to check for class imbalance.
>
> These four checks ensure the output file is clean and ready for
> Day 9 model training.

---

## Part 11: How to Run the Script

```powershell
# Step 1: Open VS Code terminal
# Step 2: Activate venv
.\venv\Scripts\activate

# Step 3: Make sure all prerequisite files exist:
#   dataset/processed/devign_ast_features.csv   (from Day 5)
#   dataset/processed/metrics_features.csv      (from Day 6)
#   dataset/processed/codebert_embeddings.csv   (from Day 7)

# Step 4: Navigate to the fusion folder
cd src\fusion

# Step 5: Run
python fuse_features.py
```

The DEMO section (Step 1) runs every time, even without real data.
It shows you the merge process on 4 hand-made samples.

The REAL FUSION (Steps 3-10) runs only when all three source files exist.

---

## Part 12: Project Architecture — Where Fusion Fits

```
                         RAW C CODE
                             |
           ┌─────────────────┼─────────────────┐
           |                 |                  |
     Day 5 AST         Day 6 Metrics     Day 7 CodeBERT
     (11 features)    (13 features)      (768 features)
           |                 |                  |
           └─────────────────┴──────────────────┘
                             |
                     DAY 8 FUSION        <-- YOU ARE HERE
                             |
               final_features.csv
             (792 features per sample)
                             |
                     Day 9 Classifier
                             |
                  Vulnerable / Non-Vulnerable
```

---

## Part 13: Feature Count Summary

| Source | Day | Features | File |
|---|---|---|---|
| AST (tree-sitter) | Day 5 | 11 | devign_ast_features.csv |
| Software Metrics | Day 6 | 13 | metrics_features.csv |
| CodeBERT Embeddings | Day 7 | 768 | codebert_embeddings.csv |
| **FUSED** | **Day 8** | **792** | **final_features.csv** |

---
*Document prepared on Day 8 — Multi-Modal Feature Fusion*
