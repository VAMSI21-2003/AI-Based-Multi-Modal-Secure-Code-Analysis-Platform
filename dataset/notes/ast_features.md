# AST Feature Extraction — Reference Document
**Project:** Multi-Modal Code Vulnerability Detection Using CodeBERT
**Day:** 5 — AST Feature Extraction
**Script:** src/ast/extract_ast_features.py

---

## Part 1: What is an Abstract Syntax Tree (AST)?

### The Plain-English Explanation

When you read the sentence:  *"The cat sat on the mat."*
you do not read it as random letters. Your brain automatically
understands:
- Subject: "The cat"
- Verb: "sat"
- Location: "on the mat"

A compiler does the same with code. When it reads:

```c
x = a + b;
```

It does not treat it as 12 random characters. It understands:
- This is an **assignment** (`=`)
- Left side: variable `x`
- Right side: a **binary expression** (`+`) with operands `a` and `b`

The compiler stores this understanding as a TREE structure:

```
assignment_expression
|-- identifier: x              (left side)
|-- operator: =
+-- binary_expression          (right side)
    |-- identifier: a
    |-- operator: +
    +-- identifier: b
```

This tree is called the **Abstract Syntax Tree** or **AST**.

**"Abstract"** means it removes unimportant details:
- Spaces are ignored
- Comments are removed
- `x=a+b` and `x = a + b` produce identical ASTs

**"Syntax"** means it captures the GRAMMAR structure of the code
(assignments, loops, conditions, function calls).

**"Tree"** means nodes are connected in a hierarchical parent-child
relationship, just like a family tree.

---

### A Complete Example: C Function to AST

**Source Code:**
```c
int add(int a, int b) {
    return a + b;
}
```

**AST Structure (simplified):**
```
translation_unit                       <- the whole file
+-- function_definition                <- "int add(...) { ... }"
    |-- primitive_type: int            <- return type
    |-- function_declarator            <- "add(int a, int b)"
    |   |-- identifier: add           <- function name
    |   +-- parameter_list            <- "(int a, int b)"
    |       |-- parameter_declaration <- "int a"
    |       |   |-- primitive_type: int
    |       |   +-- identifier: a
    |       +-- parameter_declaration <- "int b"
    |           |-- primitive_type: int
    |           +-- identifier: b
    +-- compound_statement            <- "{ return a + b; }"
        +-- return_statement          <- "return a + b;"
            +-- binary_expression     <- "a + b"
                |-- identifier: a
                |-- operator: +
                +-- identifier: b
```

Each box in this tree is called a **node**. Every node has:
- A **type** (e.g., `if_statement`, `for_statement`, `identifier`)
- A **text** (the actual source code text for that node)
- **Children** (smaller nodes that make it up)
- A **parent** (the larger node it belongs to)

---

## Part 2: Why is AST Useful for Vulnerability Detection?

### Problem with Raw Text Analysis

If you compare these two C functions as plain text, they look completely
different:

**Version 1:**
```c
for(i=0;i<n;i++){buf[i]=src[i];}
```

**Version 2:**
```c
for (i = 0; i < n; i++) {
    buf[i] = src[i];
}
```

Yet they are **identical in meaning** — both are a for-loop that copies
`n` elements from `src` into `buf`. A text-based model might treat
them as different code patterns. An AST-based model treats them as
**exactly the same structure**.

---

### What AST Captures That Text Cannot

| What we want to detect | How AST captures it |
|---|---|
| Loops (possible infinite loop or buffer overflow) | Counts `for_statement`, `while_statement`, `do_statement` nodes |
| Missing bounds check | `if_statement` count vs loop count ratio |
| Deep nesting (complex logic, often vulnerable) | `max_depth` of the AST |
| Pointer operations (use-after-free risk) | Counts `pointer_expression` nodes |
| Integer arithmetic (overflow risk) | Counts `binary_expression` nodes |
| Function complexity | `n_total_nodes` — more nodes = more complex |

---

### Research Evidence

Studies show that vulnerable functions have **statistically different**
AST feature distributions compared to safe functions:

- Vulnerable functions tend to have **more pointer operations** (higher use-after-free risk)
- Vulnerable functions tend to have **more loops relative to their if-statement count**
  (bounds checks are missing)
- Vulnerable functions tend to have **higher max depth** (more complex control flow)
- Safe functions often have **more binary expressions** (extra comparisons for bounds checking)

This is exactly what our demo showed:

| Feature | Vulnerable | Safe | Difference |
|---|---|---|---|
| n_binary_ops | 5 | 7 | Safe has MORE comparisons |
| max_depth | 9 | 10 | Safe is slightly deeper |
| n_total_nodes | 156 | 172 | Safe has more nodes |

The safe version's extra `|| src_size > sizeof(buf)` condition added
2 more binary expressions and 1 more level of depth — these are the
exact signals the model needs to learn.

---

## Part 3: What is tree-sitter?

### The Tool We Use

**tree-sitter** is a fast, accurate code parser used by major text
editors (Neovim, GitHub, VS Code) to understand and highlight code.

It can parse over 100 programming languages including C, Python, Java,
JavaScript, Rust, and Go.

**Why tree-sitter instead of Python's built-in ast module?**

Python's `ast` module only works on **Python code**. The Devign dataset
contains **C code**. tree-sitter has a C grammar (`tree-sitter-c`) that
correctly parses all C syntax including:
- Pointers (`*ptr`, `ptr->field`)
- Struct access
- Preprocessor-like constructs
- All C operators and declarations

**Installation:**
```bash
pip install tree-sitter tree-sitter-c
```

**The three key objects in tree-sitter:**

| Object | What it is | Example |
|---|---|---|
| `Language` | The grammar rules for a programming language | `Language(tsc.language())` |
| `Parser` | Reads code and builds an AST using the grammar | `Parser(C_LANGUAGE)` |
| `Node` | One node in the AST tree | `node.type`, `node.children` |

---

## Part 4: The 11 Features We Extract

### Feature Table

| Feature Name | What it counts | Why it matters for vulnerability detection |
|---|---|---|
| `n_functions` | Number of function definitions | Usually 1 per Devign sample; deviations indicate parsing issues |
| `n_loops` | `for` + `while` + `do-while` loops | Loops over buffers without bounds checks cause buffer overflows |
| `n_if_statements` | All `if` / `else if` blocks | More ifs relative to loops = more bounds checking (safer) |
| `n_assignments` | Assignment expressions (`x = ...`) | High count with pointer targets can indicate memory management issues |
| `n_returns` | Return statements | Multiple early returns sometimes bypass cleanup code |
| `n_pointer_ops` | Pointer dereferences and declarations | Direct signal for use-after-free and null dereference risk |
| `n_function_calls` | All function call expressions | Calls to `malloc`, `free`, `strcpy` are vulnerability hotspots |
| `n_binary_ops` | `+`, `-`, `*`, `/`, `==`, `<`, `>`, `&&`, etc. | More comparisons often means more bounds checking |
| `max_depth` | Deepest level in the AST | Deep nesting correlates with complex, error-prone control flow |
| `n_total_nodes` | Total count of ALL nodes | Proxy for code complexity and function length |
| `n_error_nodes` | Nodes tree-sitter could not parse | Quality check — high count means the code was malformed |

---

### What Each Feature Looks Like in C Code

**n_loops — for loop:**
```c
for (i = 0; i < n; i++) {    // one for_statement node
    buf[i] = data[i];
}
```

**n_if_statements — conditional:**
```c
if (size > MAX_SIZE) {        // one if_statement node
    return -1;
}
```

**n_pointer_ops — pointer dereference:**
```c
*ptr = value;                 // pointer_expression node
ctx->field = 42;              // pointer_expression (arrow op)
int *p = malloc(sizeof(int)); // pointer_declarator node
```

**n_assignments — assignment:**
```c
x = a + b;                    // assignment_expression node
buf[i] = src[i];              // assignment_expression node
```

**n_function_calls — call expression:**
```c
result = malloc(1024);        // call_expression node
free(ptr);                    // call_expression node
memcpy(dst, src, n);          // call_expression node
```

**n_binary_ops — binary expression:**
```c
a + b                         // binary_expression
size > MAX                    // binary_expression
x == 0 || y < 10             // two binary_expressions
```

---

## Part 5: How the Script Works — Step by Step

### Step 1 — Parser Initialization
```python
C_LANGUAGE = Language(tsc.language())  # load C grammar rules
parser = Parser(C_LANGUAGE)            # create the parser
```
This is done ONCE at startup. The same parser is reused for all ~27,000 functions.

---

### Step 2 — Parsing One Function
```python
code_bytes = code_string.encode("utf-8")  # str -> bytes
tree = parser.parse(code_bytes)            # bytes -> Tree object
root_node = tree.root_node                 # get the top node
```
tree-sitter requires bytes (not a Python string) because it works at
the binary level for performance.

---

### Step 3 — Traversing the Tree (Depth-First)

```python
def traverse_and_count(node, counts, depth=0, max_depth_ref=None):
    if depth > max_depth_ref[0]:
        max_depth_ref[0] = depth       # track deepest level seen

    counts[node.type] += 1            # count this node type

    for child in node.children:       # visit all children
        traverse_and_count(child, counts, depth + 1, max_depth_ref)
```

This is a **recursive** function — it calls itself. Think of it as
visiting every node in the tree exactly once, like reading every page
in a book in order.

**Depth-first order** for our demo vulnerable function:

```
translation_unit (depth 0)
  function_definition (depth 1)
    storage_class_specifier (depth 2)
      [static] (depth 3)
    primitive_type (depth 2)
    function_declarator (depth 2)
      identifier (depth 3)
      parameter_list (depth 3)
        ...
    compound_statement (depth 2)
      declaration (depth 3)
      ...
      for_statement (depth 3)     <- loops counted here
        ...
      if_statement (depth 3)      <- ifs counted here
        ...
```

---

### Step 4 — Mapping Counts to Feature Names

```python
FEATURE_NODE_MAP = {
    "n_loops": ["for_statement", "while_statement", "do_statement"],
    ...
}

for feature_name, node_type_list in FEATURE_NODE_MAP.items():
    features[feature_name] = sum(
        node_counts[node_type] for node_type in node_type_list
    )
```

This maps raw node type counts → named features.
`n_loops = counts["for_statement"] + counts["while_statement"] + counts["do_statement"]`

---

## Part 6: Real Output from the Demo

The script ran successfully on two hand-written C samples. Here is the
actual output:

### Vulnerable Function (label = 1)

```
Feature                    Value
---------------------------------
n_functions                    1
n_loops                        1
n_if_statements                3
n_assignments                  3
n_returns                      3
n_pointer_ops                  3
n_function_calls               2
n_binary_ops                   5
max_depth                      9
n_total_nodes                156
n_error_nodes                  0
```

### Non-Vulnerable Function (label = 0)

```
Feature                    Value
---------------------------------
n_functions                    1
n_loops                        1
n_if_statements                3
n_assignments                  3
n_returns                      3
n_pointer_ops                  3
n_function_calls               2
n_binary_ops                   7      <- 2 more comparisons
max_depth                     10      <- 1 level deeper
n_total_nodes                172      <- 16 more nodes
n_error_nodes                  0
```

### Interpretation

The safe version has 2 extra binary expressions because the bounds
check `|| src_size > sizeof(buf)` adds:
- One binary expression for `src_size > sizeof(buf)`
- One binary expression for the `||` connecting the two conditions

It also has 1 more level of nesting because the `sizeof()` call
introduces a nested node.

These small numerical differences across 27,000 samples become
strong statistical signals for the classifier.

---

## Part 7: Output Files

| File | Location | Description |
|---|---|---|
| `devign_ast_features.csv` | `dataset/processed/` | All Devign samples with 11 AST feature columns added |

### Column Structure of the Output CSV

| Column | Type | Description |
|---|---|---|
| `func` | string | Original C function source code |
| `target` | int | Label: 1=vulnerable, 0=safe |
| `project` | string | FFmpeg or qemu |
| `commit_id` | string | Git commit reference |
| `n_functions` | int | AST feature |
| `n_loops` | int | AST feature |
| `n_if_statements` | int | AST feature |
| `n_assignments` | int | AST feature |
| `n_returns` | int | AST feature |
| `n_pointer_ops` | int | AST feature |
| `n_function_calls` | int | AST feature |
| `n_binary_ops` | int | AST feature |
| `max_depth` | int | AST feature |
| `n_total_nodes` | int | AST feature |
| `n_error_nodes` | int | Parse quality indicator |
| `parse_failed` | bool | True if parsing errored |

---

## Part 8: Relevance to the Multi-Modal Architecture

This project uses a MULTI-MODAL approach — combining two types of
features:

```
C Function Source Code
        |
        |---- CodeBERT (Text Modality)
        |     - Reads the code as a sequence of tokens
        |     - Learns semantic meaning (WHAT the code does)
        |     - Output: 768-dimensional embedding vector
        |
        +---- AST Features (Structural Modality)
              - Reads the parse tree
              - Learns syntactic structure (HOW the code is organized)
              - Output: 11 numerical features

Both outputs --> Concatenated --> Classifier --> Vulnerable / Safe
```

**Why both modalities are needed:**

- CodeBERT alone might miss structural patterns (e.g., nesting depth,
  pointer count) that text does not explicitly represent.
- AST features alone miss semantic meaning (e.g., the function name
  `memcpy` being dangerous in certain contexts).
- Together, they provide complementary signals that improve detection accuracy.

---

## Part 9: Viva Questions and Answers

---

**Q1. What is an Abstract Syntax Tree (AST)?**

> An Abstract Syntax Tree is a tree-structured representation of the
> source code of a program. Each node in the tree represents a
> syntactic construct such as an if statement, a for loop, a function
> call, or an assignment. It is called "abstract" because it removes
> surface details like whitespace, comments, and formatting, retaining
> only the logical structure of the code. The AST is produced by the
> parsing stage of a compiler.

---

**Q2. Why do we use AST features instead of just raw code text for vulnerability detection?**

> Raw code text is sensitive to formatting differences — two functions
> with identical behaviour but different spacing will appear different
> to a text model. The AST normalises these differences and represents
> the structural properties of the code. Structural features such as
> the number of loops, pointer operations, and nesting depth are direct
> indicators of vulnerability patterns. For example, a loop that writes
> to a fixed buffer without a bounds check is structurally detectable
> through the ratio of loop nodes to if-statement nodes in the AST.

---

**Q3. What is tree-sitter and why did you use it?**

> tree-sitter is an open-source, language-agnostic code parser that
> produces ASTs for over 100 programming languages. We use it because
> the Devign dataset contains C code, and Python's built-in ast module
> only handles Python. tree-sitter's C grammar (tree-sitter-c package)
> correctly parses all C constructs including pointers, struct access,
> and type declarations. It is also error-tolerant — it produces a
> partial AST even for code with minor syntax issues rather than
> crashing.

---

**Q4. What is depth-first traversal and how does it work in your script?**

> Depth-first traversal is a strategy for visiting every node in a
> tree. Starting at the root, it goes as deep as possible along one
> branch before backtracking and visiting other branches. In our script,
> the traverse_and_count() function is recursive — it visits a node,
> then calls itself on each of that node's children. This ensures every
> single node in the AST is visited exactly once, and we increment the
> count for that node's type at each visit. The maximum nesting depth
> is tracked by comparing the current depth with the deepest level seen
> so far.

---

**Q5. What does max_depth tell us about a function's vulnerability?**

> max_depth measures how many levels of nesting the deepest part of
> the AST has. A high max_depth indicates deeply nested control flow
> — multiple loops inside conditions inside other conditions. Deeply
> nested code is harder for developers to reason about, more likely to
> have missed edge cases, and statistically more likely to contain
> vulnerabilities. Research has shown that vulnerable functions tend to
> have higher average AST depth compared to their fixed counterparts.

---

**Q6. What is the difference between a named node and an anonymous node in tree-sitter?**

> In tree-sitter, a named node represents a meaningful syntactic
> construct defined in the language grammar — such as if_statement,
> for_statement, or identifier. An anonymous node represents punctuation
> or keywords that have a fixed textual form — such as the { and }
> braces, the ; semicolon, or the keyword if itself. When extracting
> features, we primarily count named nodes because they represent
> the logical structure of the code, not its decoration.

---

**Q7. How do AST features complement CodeBERT in the multi-modal approach?**

> CodeBERT processes code as a sequence of tokens and learns semantic
> patterns — for example, that calling free() followed by using the
> same pointer is dangerous. However, it may miss purely structural
> signals such as overall nesting depth or the total number of pointer
> declarations. AST features capture exactly these structural properties
> as simple integers. When both feature sets are concatenated and fed
> to the classifier, the model has access to both the semantic meaning
> of the code AND its structural organisation, making it more robust
> than either modality alone.

---

## Part 10: How to Run the Script

```powershell
# Step 1: Open VS Code terminal (Ctrl + backtick)

# Step 2: Activate virtual environment
.\venv\Scripts\activate

# Step 3: Install tree-sitter (if not already done)
pip install tree-sitter tree-sitter-c

# Step 4: Navigate to the script folder
cd src\ast

# Step 5: Run the script
python extract_ast_features.py
```

**The script will:**
- Always run the demo (two sample functions) regardless of whether the dataset exists
- Process the full Devign dataset if `dataset/processed/devign_cleaned.csv` exists
- Save results to `dataset/processed/devign_ast_features.csv`

---
*Document prepared on Day 5 — AST Feature Extraction*
