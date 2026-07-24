# Phase 8 — Consistency and Formatting Audit

Performed 2026-07-24 against the drafted chapters in `report/chapters/`.

## 1. Title consistency

Checked: `AI-Based Multi-Modal Secure Code Analysis Platform` is the only title used in body content.
Grepped all of `report/chapters/*.md` for the old retired title
("Multi-Modal Code Vulnerability Detection Using CodeBERT and Structural Code Analysis") and for
"Streamlit" — **zero occurrences in any chapter**. The old title and Streamlit only appear in this
session's own planning files (`report/BLUEPRINT.md`, `report/FORMAT_SPEC.md`) as explicitly-labeled
historical context, never as the report's own title. The current title will be applied to the cover
page, certificate, and declaration in Phase 9 per `report/FORMAT_SPEC.md`'s preliminary-page templates.

## 2. No fabricated 84%-era metrics leaked in

Grepped for `84.00%`, `84%`, `0.8242`, `0.998`, and the old (wrong) split sizes `21,854`/`5,464` across
all chapters. Two matches, both correct/intentional:
- `ch7_results.md`: the only occurrence of the old figures, explicitly presented as the invalidated
  number being disclosed and corrected (Section 7.3), not as this project's result.
- `ch2_literature.md`: `21,854` refers to the **CodeXGLUE benchmark's own** train-split size (Lu et al.,
  2021) — a different, real number from an external benchmark, unrelated to this project's dataset
  split. No contamination.

All metrics elsewhere in the report trace to `models/training_metadata.json` (Accuracy 0.5932/0.5721,
F1 0.5391/0.4798, AUC-ROC 0.6346/0.5959 for XGBoost/Random Forest) per `report/BLUEPRINT.md`'s locked
ground-truth facts.

## 3. Figure numbering

Sequential, no gaps or duplicates, checked chapter-by-chapter: Figure 3.1 (1), Figure 4.1 (1),
Figures 7.1–7.12 (12, covering 4 result charts + 8 real screenshots). Fixed one issue found during this
audit: Chapter 4.1.1 referenced "Figure 4.1" as a vague "screenshot/diagram placeholder" pointing
nowhere; corrected to properly label the existing ASCII component diagram in Section 4.1.2 as Figure
4.1, removing the unresolved placeholder.

## 4. Table numbering

No chapter had explicit "Table X.Y" captions prior to this audit (markdown tables were present but
uncaptioned). Added sequential, chapter-scoped captions per `report/FORMAT_SPEC.md`'s rule (caption at
the top of the table, sentence case + bold): Table 1.1, Table 2.1, Table 3.1, Table 4.1, Tables 6.1–6.2,
Tables 7.1–7.4. All now numbered and will carry through to the Phase 9 DOCX tables.

## 5. Citations

Every in-text citation in Chapter 2 (the only chapter with citations) was checked against
`references.md`: Bessey et al. (2010), Li et al. (2018), Zhou et al. (2019), Devlin et al. (2019),
Feng et al. (2020), Lu et al. (2021), Chakraborty et al. (2020), Fu and Tantithamthavorn (2022),
Chen and Guestrin (2016), Breiman (2001), McCabe (1976), Chidamber and Kemerer (1994) — **12 citations,
12 reference entries, one-to-one correspondence, no orphans in either direction.**

## 6. Terminology consistency

Grepped for common misspellings/inconsistent forms (`Code-BERT`, `codeBERT`, `XG-Boost`, `Xgboost`) —
zero matches; `CodeBERT`, `XGBoost`, `AST`, `Random Forest` are spelled consistently throughout.

## 7. Plagiarism/originality — methodology, not a measured percentage

No plagiarism-detection tool was run against this report (none was available in this environment), so
no similarity percentage (the master prompt's "2–4%" target) can be honestly reported as *measured*.
What can be stated, and is true of the process actually followed: every sentence in every chapter was
composed fresh during this session, grounded in facts pulled directly from the project's own source
code, config files, trained-model artifacts, and test runs (cited by file path throughout), or from
externally published papers that were independently verified via web search before citation (Chapter 2)
rather than copied from this project's own pre-existing `paper/*.md` drafts. Those pre-existing drafts
were read for factual grounding only (and, where found to be unreliable — the pre-training placeholder
metrics — explicitly rejected rather than reused); no paragraph from them was copied or lightly
paraphrased into the new chapters. This is a process guarantee, not a similarity-tool measurement, and
should be described to any reader in those terms.

## 8. Formatting spec compliance — deferred to Phase 9

Font, margins, spacing, heading case/size rules, and page numbering are not yet applied (the chapters
are still in Markdown). Phase 9 assembles the DOCX against `report/FORMAT_SPEC.md`'s explicit table and
will be its own verification pass (render to PDF, visual check).
