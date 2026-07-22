# Apply-Patch → Re-Scan → Before/After Loop — Design (not implemented)

**This is a design report only — nothing described here has been built.**
Completes the remediation story end-to-end instead of AutoPatch.tsx's
current read-only diffs. Needs sign-off before any code is written, since
it's a new user-facing workflow, not a bug fix.

## 1. What "apply" actually does to the file — there usually isn't one

This is the single most important fact this design has to confront: for
most scan sources, **there is no file on disk to apply anything to.**
Verified by reading each scan path's actual code, not assumed:

| Scan source | Where the code lives | Real file on disk? |
|---|---|---|
| Paste / single-file scan | `ScanRecord.code` (DB column) only | No |
| Batch / ZIP / folder upload | `ScanRecord.code` per file (DB column) — confirmed the batch endpoint never extracts ZIP entries to disk, everything is read into memory | No |
| GitHub repo scan | Cloned to a temp dir, scanned, then `shutil.rmtree`'d in a `finally` block (`github_service.py`) | No — deleted before the response even returns |
| Watch Mode | A real local folder path (`routers/watch.py`'s `start_watch(path: ...)`) actively monitored on disk | **Yes** |

So "apply" cannot mean "write to disk" as a general mechanism — it would
only ever be possible for Watch Mode sessions. The design below treats
**apply as producing a new, derived database record** (the general case
that works for every scan source), with an optional, separate,
explicitly-confirmed disk-write step *only* for Watch Mode.

### Proposed: apply = create a derived scan record, not mutate anything

1. `recommendations.py::suggest_secure_rewrite(code)` already produces a
   complete, ready-to-use `rewritten_code` string today (used by
   CodeDiff.tsx's "Load current scan's auto-fix"). This is the natural
   input for "apply" — it's already a whole, valid rewrite, not a
   line-level diff that needs applying against a moving target.
2. An "Apply & Re-scan" action calls `ml_bridge.run_prediction()` on that
   `rewritten_code`, producing a new prediction result, and persists it as
   a **new `ScanRecord`** (same pattern every other scan entry point
   already uses) rather than overwriting the original row.
3. **Schema change required**: `ScanRecord` has no concept of "derived
   from another scan" today. A new nullable column (e.g.
   `derived_from_scan_id`) is needed to link the new record back to its
   source for the before/after comparison and for it to show up
   distinguishably in History. This is a real, additive DB schema change
   worth flagging explicitly for sign-off, not a detail to gloss over.
4. Because apply never overwrites the original record, **"revert" is
   free** — the original scan is untouched and remains exactly where it
   was; the user just navigates back to it. No explicit revert mechanism
   needs to be built.

### Watch Mode's real-file case (optional, separate, higher-risk)

Only Watch Mode has an actual file to write to. If offered at all, this
must be:
- **Opt-in and explicitly confirmed** — writing to a user's real source
  file is a destructive, hard-to-reverse action (per this session's own
  operating rules around irreversible actions), never a silent default.
- **A distinct action from "Apply & Re-scan"** above, not a variant of it
  — e.g. a separate "Write patch to disk" button, shown only when the
  active scan came from a Watch Mode session, with the file path shown
  explicitly before confirming.
- Out of scope for a first version; the DB-record-based flow (§1 items
  1–4) covers every scan source and ships real value without this risk.

## 2. How re-scan is triggered

**User-initiated, not automatic.** A single "Apply & Re-scan" button,
consistent with how every other action in this app already works (nothing
currently auto-runs in the background without a click) — no silent
rewrite-then-rescan on page load or on a timer.

### Pre-condition / disabled states

- If `suggest_secure_rewrite(code)["changed"]` is `False` (no fixable
  pattern found), there's nothing to apply — the button should be absent
  or disabled, not produce a no-op scan.
- If `requires_manual_sizing` is `True` (see `docs/CI_CD.md`-adjacent
  honesty pattern in this codebase — some fixes are honest placeholders
  like `strncpy(dest, src, dest_size - 1); /* TODO: set dest_size to
  dest's real capacity */`, not valid, compilable C), applying and
  re-scanning that text would feed the model a snippet containing literal
  template/comment text, not real fixed code — a misleading comparison.
  **The button should warn or block in this case**, not silently proceed
  as if the fix were complete. This is a real, concrete edge case this
  codebase's own `patch_safety.py` module already exists specifically to
  be honest about, and the apply-patch flow must not undo that honesty by
  auto-applying an incomplete template.

## 3. What the before/after comparison shows, and where

**Reuse existing components, don't build new ones for this:**

- **Verdict/risk/probability delta** — the same side-by-side comparison
  pattern `ModelComparison.tsx` already implements for XGBoost vs. Random
  Forest, applied instead to original-scan vs. derived-scan. Same shape of
  data (two `ScanResult`-like objects), same visual treatment.
- **Code diff** — `DiffViewer.tsx` (already built, already used by
  `CodeDiff.tsx`) rendering original code vs. `rewritten_code`. No new
  diff-rendering component needed.
- **Placement**: a natural fit is directly on `AutoPatch.tsx` (where the
  fix originates) — after applying, show the before/after comparison
  inline on that same page rather than navigating away, so the loop
  (see a problem → apply → see the result) stays in one place. An
  alternative is surfacing it as a new tab/section on `Analysis.tsx`
  alongside the existing scan detail — worth a explicit choice at sign-off
  rather than assuming.

## 4. Edge cases

- **Patch "fails to apply cleanly"**: doesn't really apply in the
  traditional sense here, since there's no live file being patched against
  a moving target — `rewritten_code` is a complete, already-computed
  string, not a diff applied against something that could have changed
  underneath it. The closest real equivalent is the
  `requires_manual_sizing` case above (§2), already covered.
- **Re-scan finds new/different issues**: entirely possible and should be
  shown honestly, not hidden — e.g. the regex-based rewrite fixes the
  targeted pattern but the model's semantic score moves in an unexpected
  direction (this session's own investigation found a real example of the
  model scoring a "safer," more structurally complex rewrite *higher*
  risk than the original — see `docs/CI_CD.md` §4). The before/after
  comparison must display this plainly rather than assuming "after" is
  always "better."
- **User wants to revert**: free, per §1.4 — the original record is
  never touched.
- **Applying twice / re-applying an already-derived scan**: the derived
  scan's own `suggest_secure_rewrite` may find nothing left to fix
  (`changed: False`) once the obvious pattern is gone — the disabled-button
  state in §2 already covers this naturally, no special-case needed.

## 5. Open questions for sign-off

1. Confirm "apply = new DB record, not a file write" as the general
   mechanism (§1), and confirm the Watch Mode real-file-write option is
   out of scope for a first version.
2. Confirm the `derived_from_scan_id` schema addition.
3. Confirm UI placement: inline on AutoPatch.tsx vs. a new section
   elsewhere (§3).
4. Confirm the block/warn behavior for `requires_manual_sizing` cases
   (§2) rather than silently allowing apply on an incomplete template.
