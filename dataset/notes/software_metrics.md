# Software Metrics — Reference Document
**Project:** Multi-Modal Code Vulnerability Detection Using CodeBERT
**Day:** 6 — Software Metrics Extraction
**Script:** src/metrics/extract_metrics.py

---

## Part 1: What Are Software Metrics?

### The Everyday Analogy

When a doctor assesses your health, they do not read your full medical
history from scratch every time. Instead, they take simple, fast
measurements — blood pressure, heart rate, temperature, weight — and
use these numbers to form a quick picture of your condition.

Software metrics do the same for source code. They are NUMBERS that
describe measurable properties of a program without requiring a deep
understanding of what the code actually does.

**Examples of what a software metric measures:**

| Question about the code | Metric that answers it |
|---|---|
| How big is this function? | Lines of Code (LOC) |
| How repetitive is it? | Loop Count |
| How much conditional logic does it have? | If Statement Count |
| How deeply nested is it? | Nesting Depth |
| How well documented is it? | Comment Count |
| How long are individual lines? | Average Line Length |

---

### What Software Metrics Are NOT

Software metrics do NOT tell you:
- The MEANING of the code (what it does logically)
- Whether a specific algorithm is correct
- The variable names or function names used

For those, we need CodeBERT (semantic text analysis) and AST features
(structural analysis). Metrics are the SIMPLEST, FASTEST layer of the
multi-modal system — a quick numerical fingerprint of the code.

---

### Where Do Metrics Come From?

Metrics are computed directly from the raw code STRING using:
- **String operations** — counting lines, measuring lengths
- **Regular expressions (regex)** — pattern matching to find keywords

No external parser is needed. This makes metrics:
- **Extremely fast** — thousands of functions per second on a CPU
- **Transparent** — every metric can be explained and verified manually
- **Robust** — works even on partially broken or unusual code

---

## Part 2: The 13 Metrics Extracted

### CORE METRICS (8 requested)

---

#### Metric 1: Lines of Code (LOC)

**What it counts:** Non-empty lines — lines that contain at least one
non-whitespace character.

**How it is computed:**
```python
non_empty = [line for line in code.split('\n') if line.strip() != '']
loc = len(non_empty)
```

**Example:**
```c
static int decode(uint8_t *src) {    // line 1
    uint8_t buf[1024];               // line 2
                                     // (blank — not counted)
    return process(buf);             // line 3
}                                    // line 4
// LOC = 4
```

**Why it matters for vulnerability detection:**
Research consistently shows that larger functions (higher LOC) carry
more bugs in absolute terms. A 400-line function has more opportunities
to hide a missing bounds check than a 20-line function. LOC is the
single most commonly used software metric in bug prediction research.

---

#### Metric 2: Function Count

**What it counts:** C function definitions — places where a named block
of code is declared with a return type, name, parameters, and a body.

**How it is computed:**
```python
pattern = r'\b([a-zA-Z_]\w*)\s*\([^;{]*\)\s*\{'
matches = re.findall(pattern, code)
count = sum(1 for name in matches if name not in c_keywords)
```

**Why it matters:** In the Devign dataset, each sample is already one
function, so this metric is almost always 1. Deviations (0 or 2)
indicate unusual samples or extraction errors — useful as a data
quality signal. In general code analysis, high function count per
file indicates good modularisation.

---

#### Metric 3: Loop Count

**What it counts:** All three types of C loops combined.

| Loop Type | C Syntax | Keyword Matched |
|---|---|---|
| For loop | `for (init; cond; step) { }` | `for\s*(` |
| While loop | `while (condition) { }` | `while\s*(` |
| Do-While loop | `do { } while (condition);` | `do\b` |

**Example:**
```c
for (i = 0; i < n; i++) { ... }    // loop_count += 1
while (ptr != NULL) { ... }         // loop_count += 1
do { ... } while (x > 0);          // loop_count += 1
// loop_count = 3
```

**Why it matters:**
Loops are the primary context for buffer overflow vulnerabilities.
A loop that writes to a fixed-size array (`buf[i] = src[i]`) must
check that `i` never exceeds the array size. A high loop count without
a proportionally high if-count suggests bounds checks may be missing.

**Key ratio to watch:**
```
loop_count / if_count
```
Vulnerable functions tend to have a HIGHER ratio (more loops relative
to conditional checks). Safe functions tend to have a LOWER ratio
(every loop has one or more guard conditions).

---

#### Metric 4: If Statement Count

**What it counts:** All `if` and `else if` statements.

```python
count = len(re.findall(r'\bif\s*\(', code))
```

**Example:**
```c
if (size <= 0) return -1;              // if_count += 1
if (size > MAX || ptr == NULL) { }     // if_count += 1
else if (mode == FAST) { }             // if_count += 1
// if_count = 3
```

**Why it matters:**
If statements represent decision points — the developer is checking
a condition before proceeding. In security-critical code:
- `if (ptr == NULL)` — null pointer guard
- `if (size > BUFFER_MAX)` — bounds check
- `if (result < 0)` — error handling

More if statements = more defensive programming = generally safer code.
This is why the RATIO of `if_count / loop_count` is a useful feature.

---

#### Metric 5: Return Statement Count

**What it counts:** All occurrences of the `return` keyword.

```python
count = len(re.findall(r'\breturn\b', code))
```

**Example:**
```c
if (size < 0)    return AVERROR;    // return_count += 1
if (ptr == NULL) return -1;         // return_count += 1
return process(buf);                // return_count += 1
// return_count = 3
```

**Why it matters:**
Multiple early return statements indicate complex control flow with
many exit paths. Each exit path must properly clean up any resources
(memory, file handles, locks) allocated before it. Missing cleanup
on an early return path is the classic cause of memory leaks.

A function with 8 return statements and 3 `free()` calls should be
carefully audited — some return paths probably miss the `free()`.

---

#### Metric 6: Average Line Length

**What it counts:** The mean character count across all non-empty lines.

```python
non_empty = [line for line in code.split('\n') if line.strip()]
avg = sum(len(line) for line in non_empty) / len(non_empty)
```

**Why it matters:**
Very long average line length indicates:
- Complex expressions packed into single lines (harder to audit)
- Long format strings with injection potential
- Deeply nested code (each level of nesting adds indentation = length)

Industry coding standards (Google C++ Style, Linux Kernel) recommend
a maximum line length of 80 characters. Functions that consistently
exceed this may have readability — and security — problems.

---

#### Metric 7: Maximum Line Length

**What it counts:** The character count of the longest single line.

```python
max_len = max(len(line) for line in code.split('\n'))
```

**Why it matters:**
Extremely long lines (200+ characters) are almost never reviewed
carefully in code audits. A vulnerability hiding in a 250-character
line has a much lower chance of being spotted by a human reviewer.

---

#### Metric 8: Comment Count

**What it counts:** All C comment blocks.

| Comment Type | Syntax | Regex Pattern |
|---|---|---|
| Single-line | `// text` | `//[^\n]*` |
| Multi-line | `/* text */` | `/\*.*?\*/` with DOTALL flag |

**Example:**
```c
// allocate output buffer         ← comment_count += 1
/* the caller must free
   this memory when done */       ← comment_count += 1
int *buf = malloc(size);
// comment_count = 2
```

**Why it matters:**
Well-commented code indicates a developer who:
1. Understood what they were writing
2. Cared about others understanding it
3. Likely thought through edge cases

Research shows that poorly-commented complex code has a higher bug
density. When comment_count is LOW and nesting_depth + loop_count are
HIGH, the function is complex AND poorly explained — a high-risk signal.

---

### BONUS METRICS (5 additional)

---

#### Metric 9: Total Lines

All lines in the function including blank lines.
`total_lines = loc + blank_lines`

---

#### Metric 10: Blank Line Count

Lines containing only whitespace.
`blank_lines = total_lines - loc`

The ratio `blank_lines / total_lines` indicates code density.
Developers who write many blank lines between logical sections
tend to write more readable, carefully structured code.

---

#### Metric 11: Nesting Depth

**How it is computed:** We scan character-by-character, incrementing
a counter at each `{` and decrementing at each `}`. The maximum value
ever reached is the nesting depth.

```
void f() {              depth 1
    if (x) {            depth 2
        for (...) {     depth 3   ← max_depth = 3
        }               depth 2
    }                   depth 1
}                       depth 0
```

**Why it matters:**
McCabe's Cyclomatic Complexity (a well-known research metric) is
directly related to nesting depth — deeper nesting means more
independent execution paths, more opportunities for a missed check.

---

#### Metric 12: Operator Count

Counts arithmetic, comparison, and logical operators:
`++`, `--`, `+=`, `-=`, `*=`, `/=`, `==`, `!=`, `<=`, `>=`, `&&`, `||`, `<<`, `>>`

**Why it matters:**
Integer overflow vulnerabilities involve arithmetic operators applied
to values without range checking. A high count of `*` and `<<`
operators (bitshift and multiplication) in a function that works with
user-provided sizes is a risk signal. The `<<` operator doubles a value
each time and can rapidly exceed integer limits.

---

#### Metric 13: Pointer Count

Counts `->` (arrow operator) and `*identifier` (pointer dereference).

**Why it matters:**
Every pointer dereference in C is a potential crash or exploitation
point if the pointer is:
- NULL (null dereference → crash)
- Freed (use-after-free → exploitation)
- Out-of-bounds (buffer overread → information leak)

A function with a high pointer count that also has a low if-count
is suspicious — the pointers are not being validated.

---

## Part 3: Real Output from the Demo

The script ran on two hand-written C samples. Here are the actual
results printed by the script:

```
Metric                 Vulnerable     Safe      Change
-------------------------------------------------------
loc                            20       24          +4  <-- differs
function_count                  1        1           0
loop_count                      1        1           0
if_count                        3        3           0
return_count                    3        3           0
avg_line_length             30.45    31.17       +0.72  <-- differs
max_line_length                65       65           0
comment_count                   2        3          +1  <-- differs
total_lines                    24       28          +4  <-- differs
blank_lines                     4        4           0
nesting_depth                   2        2           0
operator_count                  3        4          +1  <-- differs
pointer_count                   6        6           0
```

### What the Numbers Reveal

The safe version has:
- **+4 more LOC** — the extra error log line and the extended if condition
- **+1 more comment** — the developer added an explanatory comment
- **+1 more operator** — the added comparison `src_size > sizeof(buf)`

Most other metrics are IDENTICAL between the two versions. This shows
that software metrics alone are not always sufficient — the structural
difference (missing one comparison) is small. This is exactly why the
project uses a MULTI-MODAL approach: combining metrics with AST features
and CodeBERT embeddings captures patterns that no single approach sees.

---

## Part 4: How Software Metrics Fit in the Project Architecture

```
C Function (raw code string)
        |
        |
        +-------> METRICS BRANCH (today, Day 6)
        |         Uses: regex, string counting
        |         Speed: very fast (microseconds per function)
        |         Output: 13 numeric features per function
        |
        +-------> AST BRANCH (Day 5)
        |         Uses: tree-sitter C parser
        |         Speed: fast (milliseconds per function)
        |         Output: 11 structural features per function
        |
        +-------> CodeBERT BRANCH (Day 8)
                  Uses: CodeBERT transformer model
                  Speed: slow (seconds per function, GPU recommended)
                  Output: 768-dimensional embedding vector

All three outputs --> Combined --> Classifier --> Vulnerable / Safe
```

Each branch contributes different types of information:

| Branch | What it captures | Example signal |
|---|---|---|
| Metrics | Simple statistics | LOC=250, loop=5, comment=0 |
| AST | Tree structure | 5 loops, 8 pointer nodes, depth=7 |
| CodeBERT | Semantic meaning | "memcpy without size check" pattern |

Together, they provide a comprehensive picture that no single approach
can match alone.

---

## Part 5: Advantages of Software Metrics

| Advantage | Explanation |
|---|---|
| No parser needed | Only uses basic string operations and regex |
| Language-portable | Similar metrics can be defined for Python, Java, etc. |
| Fast to compute | Millions of functions can be analysed per hour on a CPU |
| Interpretable | Every metric can be explained to a non-technical person |
| Research-backed | LOC, cyclomatic complexity, comment density have decades of literature |
| No GPU required | Suitable for MCA-level project without cloud resources |
| Transparent | If the model uses a metric, you can say exactly what it counts |

---

## Part 6: Limitations of Software Metrics

| Limitation | Explanation |
|---|---|
| No semantic meaning | Metrics do not know WHAT the code does — only HOW MUCH |
| Formatting sensitivity | A one-liner vs multi-line equivalent gives different LOC |
| Regex inaccuracy | Keyword matching inside strings or comments can give false counts |
| No context | A high pointer count in a list traversal is very different from one in a memory allocator |
| Weak alone | No single metric reliably predicts vulnerability — must be combined |
| C-style bias | Metrics like pointer_count are meaningful for C but not for Python |

---

## Part 7: Output File

| File | Location | Description |
|---|---|---|
| `metrics_features.csv` | `dataset/processed/` | All Devign samples with 13 metric columns added |

### Column Reference

| Column | Type | Description |
|---|---|---|
| `func` | string | Original C function source code |
| `target` | int | Label: 1=vulnerable, 0=safe |
| `project` | string | FFmpeg or qemu |
| `commit_id` | string | Git commit reference |
| `loc` | int | Non-empty line count |
| `function_count` | int | Function definition count |
| `loop_count` | int | Total loop count |
| `if_count` | int | If statement count |
| `return_count` | int | Return statement count |
| `avg_line_length` | float | Mean line length (non-empty lines) |
| `max_line_length` | int | Longest line length |
| `comment_count` | int | Comment block count |
| `total_lines` | int | All lines including blank |
| `blank_lines` | int | Blank/whitespace-only lines |
| `nesting_depth` | int | Approximate max brace depth |
| `operator_count` | int | Arithmetic/comparison operator count |
| `pointer_count` | int | Pointer dereference count |

---

## Part 8: Viva Questions and Answers

---

**Q1. What is a software metric and how is it different from a code feature?**

> A software metric is a numerical measurement of a property of source
> code — such as its size (lines of code), complexity (nesting depth),
> or documentation quality (comment count). A code feature is a broader
> term for any input value used by a machine learning model. Software
> metrics are one TYPE of code feature. Other feature types in this
> project include AST structural features (from tree-sitter parsing)
> and semantic embedding features (from CodeBERT). The distinction is
> that metrics are computed using simple counting and pattern matching,
> while other feature types require a parser or a neural network.

---

**Q2. Why is Lines of Code (LOC) a useful vulnerability predictor?**

> Research spanning several decades consistently shows that functions
> with more lines of code contain more bugs in absolute terms, even
> if the bug DENSITY (bugs per line) may decrease. This is because
> larger functions are harder to reason about, more difficult to
> audit manually, and more likely to have complex control flow with
> missed edge cases. In the Devign dataset, vulnerable functions
> tend to have a higher average LOC than their fixed non-vulnerable
> counterparts. LOC is the most widely studied metric in software
> defect prediction literature.

---

**Q3. What is a regular expression (regex) and how do you use it to count loops?**

> A regular expression is a pattern written in a special syntax that
> describes what a text string should look like. Python's `re` module
> uses these patterns to search inside strings. To count `for` loops,
> we use the pattern `\bfor\s*\(`, which means: a word boundary (so we
> do not match `enforce`), then the word `for`, then optional spaces
> `\s*`, then an opening parenthesis `\(`. Every match of this pattern
> in the code string corresponds to one `for` loop. We use `re.findall`
> to return all matches and then call `len()` on the result to count them.

---

**Q4. Why does the comment_count metric matter in vulnerability detection?**

> Comment count serves as a proxy for developer care and code
> understandability. Functions with complex logic — many loops, pointer
> operations, or deeply nested conditions — but very few or no comments
> indicate that the developer wrote the code without fully documenting
> their reasoning. Such functions are harder to review, harder to
> maintain, and statistically more likely to contain undetected errors.
> Empirical studies in software engineering have found that low comment
> density in complex functions correlates with higher defect rates.
> In our analysis, the safe version of our demo function had one more
> comment than the vulnerable version, supporting this observation.

---

**Q5. What is nesting depth and why does a high value indicate higher risk?**

> Nesting depth measures how many levels deep the innermost code is
> inside nested control structures such as if, for, while, and switch
> blocks. Each opening brace `{` increases the depth by one; each
> closing brace `}` decreases it. A nesting depth of 1 means code is
> inside only one block (the function body). A depth of 6 means code
> is inside six nested blocks. High nesting depth indicates complex,
> branching logic. McCabe's Cyclomatic Complexity — a well-established
> academic metric — is directly related to the number of independent
> paths through a function, which grows with nesting depth. Highly
> nested code is difficult to reason about and easy to make mistakes in,
> particularly around resource management and bounds checking.

---

**Q6. What is the loop-to-if ratio and why is it useful?**

> The loop-to-if ratio is computed by dividing loop_count by if_count
> for a given function. A high ratio (many loops, few ifs) suggests
> that the developer has written repetitive operations over data without
> proportionally many bounds checks or guard conditions. This is the
> typical pattern seen in buffer overflow vulnerabilities — a loop
> writes to a fixed-size buffer, but there is no `if` statement to
> check that the loop index does not exceed the buffer size. A lower
> ratio (many ifs relative to loops) suggests that more care has been
> taken to validate inputs and check boundary conditions before
> accessing memory. This ratio is not used as a standalone classifier,
> but as one of several combined features.

---

**Q7. Why do we use multiple metrics together instead of relying on just one?**

> No single metric is reliable enough to predict vulnerability on its
> own. A function can have a high LOC but be very well-structured and
> safe. A function can have few loops but a critical use-after-free bug.
> By combining 13 metrics together, we capture a multi-dimensional
> picture of the function's complexity, documentation quality, and
> structural characteristics. When fed to a machine learning classifier,
> these 13 numbers together provide statistical patterns that correlate
> with vulnerability even when no single metric does. This is the same
> principle behind medical diagnosis — blood pressure alone does not
> diagnose heart disease, but blood pressure combined with cholesterol,
> heart rate, and age gives a much more reliable prediction.

---

## Part 9: How to Run

```powershell
# Step 1: Open VS Code terminal (Ctrl + backtick)

# Step 2: Activate virtual environment
.\venv\Scripts\activate

# Step 3: Navigate to the script folder
cd src\metrics

# Step 4: Run the script
python extract_metrics.py
```

The script runs the **demo** (two sample functions) on every execution.
Full dataset processing runs only if `dataset/processed/devign_cleaned.csv`
exists (produced by Day 4's preprocessing script).

---
*Document prepared on Day 6 — Software Metrics Extraction*
