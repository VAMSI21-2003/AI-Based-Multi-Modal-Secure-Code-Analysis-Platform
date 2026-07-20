# Sample Analysis — Devign Dataset
**Project:** Multi-Modal Code Vulnerability Detection Using CodeBERT
**Day:** 4 — Dataset Understanding
**Date:** 2026-06-14

---

## Purpose of This Document

Before preprocessing any dataset, a researcher must understand WHAT the data looks like.
This document examines real-style samples from the Devign dataset — both vulnerable and
non-vulnerable — and explains exactly WHY each sample is or is not vulnerable.

Understanding these patterns is critical because:
1. It helps us verify that the dataset is meaningful.
2. It tells us what PATTERNS the model needs to learn.
3. It helps us write the right preprocessing steps without accidentally erasing
   important structural signals in the code.

---

## What a Devign Sample Looks Like (Raw JSON)

Each sample in `function.json` is a JSON dictionary with exactly 4 fields:

```json
{
  "func"      : "static int decode_frame(AVCodecContext *avctx, ...) { ... }",
  "target"    : 1,
  "project"   : "FFmpeg",
  "commit_id" : "a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2"
}
```

| Field | Meaning |
|---|---|
| `func` | The complete C function — this is the INPUT to our model |
| `target` | 0 = safe, 1 = vulnerable — this is the LABEL (what the model must predict) |
| `project` | Either "FFmpeg" or "qemu" — tells us the source |
| `commit_id` | The Git commit hash — used to trace back to the original fix |

---

## Sample Analysis 1 — VULNERABLE (Buffer Overflow)

```c
static int hq_decode_frame(AVCodecContext *avctx, AVFrame *frame,
                            const uint8_t *src, int src_size)
{
    HQContext *ctx = avctx->priv_data;
    uint8_t   buf[1024];
    int        i;

    if (src_size <= 0)
        return AVERROR_INVALIDDATA;

    for (i = 0; i < src_size; i++) {
        buf[i] = src[i] ^ ctx->key;
    }

    return ff_hq_process(ctx, frame, buf, src_size);
}
```

**Label:** `1` — Vulnerable

**Vulnerability Type:** Buffer Overflow (Stack-based)

**Why it is vulnerable:**

The local array `buf` is declared with a fixed size of 1024 bytes. The `for` loop then
writes `src_size` bytes into `buf` — one byte per iteration. The problem is that `src_size`
is an untrusted value received from outside the function (e.g., from a media file or
network packet), and the only check is `if (src_size <= 0)`.

If an attacker provides a file where `src_size = 2000`, the loop will run 2000 iterations
and write 2000 bytes into a 1024-byte buffer. The extra 976 bytes overflow onto the stack,
potentially overwriting the saved return address, which allows an attacker to redirect
program execution.

**The missing fix:**
```c
// This one check would have made the function safe:
if (src_size <= 0 || src_size > 1024)
    return AVERROR_INVALIDDATA;
```

**What the model must learn from this sample:**
- A fixed-size buffer (`buf[1024]`) being written in a loop controlled by an external
  variable (`src_size`) without an upper-bound check is a dangerous pattern.
- The presence of only a lower-bound check (`> 0`) but absence of an upper-bound check
  (`< 1024`) is the key vulnerability signal.

---

## Sample Analysis 2 — NON-VULNERABLE (Safe Version of Sample 1)

```c
static int hq_decode_frame(AVCodecContext *avctx, AVFrame *frame,
                            const uint8_t *src, int src_size)
{
    HQContext *ctx = avctx->priv_data;
    uint8_t   buf[1024];
    int        i;

    if (src_size <= 0 || src_size > sizeof(buf)) {
        av_log(avctx, AV_LOG_ERROR,
               "Invalid source size: %d\n", src_size);
        return AVERROR_INVALIDDATA;
    }

    for (i = 0; i < src_size; i++) {
        buf[i] = src[i] ^ ctx->key;
    }

    return ff_hq_process(ctx, frame, buf, src_size);
}
```

**Label:** `0` — Non-Vulnerable

**Why it is safe:**

The developer added an **upper-bound check** using `sizeof(buf)`. `sizeof(buf)` evaluates
to 1024 at compile time. So the condition now reads: "if src_size is 0 or negative, OR
if src_size is greater than 1024, reject the input."

This means the loop can only ever write at most 1024 bytes — exactly how large the buffer
is. It is now impossible to overflow the buffer regardless of what input an attacker provides.

**What the model must learn from this sample:**
- The same buffer + loop structure as Sample 1, but the ADDITION of `|| src_size > sizeof(buf)`
  makes it completely safe.
- The model should learn that checking both sides (lower AND upper bound) of an external
  size parameter before a fixed buffer write is the hallmark of safe code.

---

## Sample Analysis 3 — VULNERABLE (Use After Free)

```c
static void mpeg_mux_end_stream(AVFormatContext *s)
{
    MpegMuxContext *ctx = s->priv_data;
    StreamInfo     *stream;
    int             i;

    for (i = 0; i < ctx->nb_streams; i++) {
        stream = ctx->streams[i];
        av_free(stream->buffer);          /* buffer memory is freed */
        av_free(stream);                  /* stream itself is freed */
    }

    if (ctx->needs_flush) {
        for (i = 0; i < ctx->nb_streams; i++) {
            flush_stream(ctx->streams[i]);  /* streams[i] is already freed! */
        }
    }

    av_free(ctx->streams);
}
```

**Label:** `1` — Vulnerable

**Vulnerability Type:** Use After Free

**Why it is vulnerable:**

In the first loop, `av_free(stream)` releases the memory that `ctx->streams[i]` points to.
However, the pointer `ctx->streams[i]` still holds the old memory address — it is now a
"dangling pointer". In the second loop (inside `if ctx->needs_flush`), `flush_stream(ctx->streams[i])`
is called using these dangling pointers.

At this point, the freed memory may have been reallocated by another part of the program.
`flush_stream` will read and write into this recycled memory, causing data corruption or
allowing an attacker to control what data is placed at that memory address before the second
loop runs.

**The missing fix:**
```c
av_free(stream->buffer);
av_free(stream);
ctx->streams[i] = NULL;   /* set to NULL immediately after freeing */
```

Setting a pointer to `NULL` after freeing it ensures that any later use of the pointer
is immediately caught as a crash (null pointer dereference) rather than silently corrupting
memory.

**What the model must learn from this sample:**
- When `av_free()` or `free()` is called on a pointer and that same pointer is used again
  later in the same function without being set to NULL, it is a Use-After-Free pattern.
- Two separate loops operating on the same array of pointers — where the first frees and
  the second reads — is a structural red flag.

---

## Sample Analysis 4 — VULNERABLE (Integer Overflow)

```c
static int allocate_frame_buffer(AVCodecContext *avctx, AVFrame *frame)
{
    int width  = avctx->width;
    int height = avctx->height;
    int size;

    size = width * height * 4;   /* 4 bytes per pixel (RGBA) */

    frame->data[0] = av_malloc(size);
    if (!frame->data[0])
        return AVERROR(ENOMEM);

    memset(frame->data[0], 0, size);
    return 0;
}
```

**Label:** `1` — Vulnerable

**Vulnerability Type:** Integer Overflow leading to Heap Buffer Overflow

**Why it is vulnerable:**

`width`, `height`, and the constant `4` are all `int` (32-bit signed integers). The
maximum value of a 32-bit signed integer is 2,147,483,647.

If an attacker provides `width = 50000` and `height = 50000`:
```
50000 * 50000 = 2,500,000,000   (exceeds 2,147,483,647)
```

This overflows a 32-bit int and wraps around to a NEGATIVE or very small number. `av_malloc`
then allocates a tiny buffer (or fails silently). But `memset` still tries to write
`size` bytes — and since `size` has wrapped around, the behavior is undefined and the
heap gets corrupted.

**The missing fix:**
```c
/* Check before multiplying */
if (width > 0 && height > 0 && width <= INT_MAX / (height * 4)) {
    size = width * height * 4;
} else {
    return AVERROR_INVALIDDATA;
}
```

**What the model must learn from this sample:**
- Multiplication of two user-controlled integer values (`width * height`) without overflow
  checking before use in `malloc` is a classic integer overflow pattern.
- The vulnerability is subtle: the code LOOKS safe (it checks `if (!frame->data[0])`) but
  the problem happens BEFORE the malloc call, in the multiplication.

---

## Sample Analysis 5 — NON-VULNERABLE (Correct Integer Handling)

```c
static int allocate_frame_buffer(AVCodecContext *avctx, AVFrame *frame)
{
    int      width  = avctx->width;
    int      height = avctx->height;
    int64_t  size;   /* use 64-bit integer to prevent overflow */

    if (width <= 0 || height <= 0) {
        av_log(avctx, AV_LOG_ERROR, "Invalid dimensions\n");
        return AVERROR_INVALIDDATA;
    }

    size = (int64_t)width * height * 4;

    if (size > INT_MAX) {
        av_log(avctx, AV_LOG_ERROR, "Frame too large\n");
        return AVERROR_INVALIDDATA;
    }

    frame->data[0] = av_malloc((size_t)size);
    if (!frame->data[0])
        return AVERROR(ENOMEM);

    memset(frame->data[0], 0, (size_t)size);
    return 0;
}
```

**Label:** `0` — Non-Vulnerable

**Why it is safe:**

The developer made three changes:

1. `int64_t size` — uses a 64-bit integer, which can hold values up to 9.2 quintillion,
   preventing overflow during multiplication.
2. `(int64_t)width * height * 4` — the cast to `int64_t` before the multiplication forces
   the entire arithmetic to be done in 64-bit, preventing intermediate overflow.
3. `if (size > INT_MAX)` — an explicit check rejects frames that are too large before
   attempting allocation.

**What the model must learn from this sample:**
- The SAME arithmetic operation as Sample 4, but using `int64_t` and explicit overflow
  checks makes it completely safe.
- The model should learn that 64-bit integer types and pre-multiplication bounds checks
  are safety signals.

---

## Summary: Patterns the Model Must Learn

| Pattern | Vulnerable Signal | Safe Signal |
|---|---|---|
| Fixed buffer + external size | No upper bound check | `size > sizeof(buf)` check present |
| Pointer after free | Pointer used after `free()` | Pointer set to `NULL` after `free()` |
| Integer multiplication for malloc | Result stored in `int` | Result stored in `int64_t` |
| User-controlled array index | Index used without range check | Explicit `index < array_size` check |
| Memory allocation result | Allocation result never checked | `if (!ptr) return error` present |

These are the patterns that CodeBERT (text modality) and structural analysis (AST/CFG modality)
will learn to detect during training.

---
*Analysis prepared on Day 4 — Dataset Understanding and Preprocessing*
