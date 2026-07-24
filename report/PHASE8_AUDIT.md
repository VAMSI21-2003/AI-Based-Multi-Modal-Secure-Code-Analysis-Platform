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

## 8. Formatting spec compliance — verified after Phase 9

Font, margins, spacing, heading case/size rules, and page numbering are applied per
`report/FORMAT_SPEC.md`. Verified 2026-07-24 by rendering `Final_Report.docx` to PDF and checking it
directly (not just trusting the XML):

- **Page border**: `report/MCA_4sem_Project_Report_format.docx` was rendered to PDF and its
  `word/document.xml` inspected directly — single black rule, `sz=24` (3pt), `space=24` (24pt offset
  from the page edge). The same border is now written into all 3 `w:sectPr` sections of
  `Final_Report.docx` (`assemble_docx.py::add_page_border`, called once per section — a border set on
  only one section would not appear on the others' pages). Confirmed identical on a front-matter page,
  an early content page, a late content page, and the final page.
- **Fonts**: python-docx's default template bakes Cambria into every Heading/Title style and Calibri
  into Normal/List/TOC styles via theme font references, independent of any direct run-level
  formatting — this was the actual root cause, not a missed run. Fixed by forcing Times New Roman at
  the *style* level for every style in use (`force_all_style_fonts`), pre-defining `TOC 1/2/3` styles
  before Word ever populates the TOC field, and a belt-and-suspenders raw-XML purge
  (`purge_theme_fonts_from_docx` / `report/purge_fonts.py`) run both after the initial build and again
  after Word's own TOC-field update (which reintroduced a theme font reference on the generated TOC
  entry runs the first time — the second purge pass catches exactly this). Verified with the real
  `pdffonts` tool (poppler): only Times New Roman (regular/bold/italic), Consolas (intentional, code
  blocks), and Symbol/Arial (unavoidable bullet-point glyphs) appear — zero Cambria, zero Calibri.
- **Diagrams**: Figure 3.1 (offline training pipeline) and Figure 4.1 (system architecture) were
  monospace ASCII box-and-arrow art; replaced with real matplotlib-generated PNG diagrams
  (`report/figures/fig_pipeline_offline.png`, `fig_architecture.png`) with proper captions. A real bug
  was caught during this fix: Figure 4.1's caption originally wrapped across two lines in the markdown
  source, which silently broke the parser's single-line caption regex and dropped the image entirely
  (the stray `(`path`)` text leaked into the body text instead) — fixed by keeping the caption on one
  line, matching the pattern used successfully elsewhere, and reverified by re-rendering the page.
- **Word/page count**: Word's own `ComputeStatistics` reports 11,743 words across 58 pages in the final
  render (an independent PyMuPDF text-extraction count over the same PDF gives 12,123 words, the
  difference being normal tokenization differences between the two tools — both are real counts from
  the actual rendered document, neither is estimated).
