
# -*- coding: utf-8 -*-
"""
Assembles report/Final_Report.docx from report/chapters/*.md, following
report/FORMAT_SPEC.md exactly:
  - A4, Times New Roman, margins Top 1" Bottom 1" Left 1.5" Right 1"
  - Body text 12pt normal, 1.5 line spacing
  - Chapter No.: 18pt Sentence case + Bold; Chapter TITLE: 18pt Capital case + Bold
  - First level heading (N.M): 16pt Capital case + Bold
  - Second level heading (N.M.K): 14pt Sentence case + Bold (kept as authored Title Case
    to avoid mangling proper nouns/acronyms like CodeBERT, XGBoost, AST, FastAPI)
  - Table caption: 12pt Sentence case + Bold, at TOP of table
  - Figure caption: 12pt Sentence case + Bold, at BOTTOM of figure
  - Page numbers: bottom right; preliminary pages i, ii, iii...; chapters+references 1,2,3...
Personal fields (student name, USN, guide, viva date) are left as bracketed
placeholders -- never invented.
"""
import re
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from PIL import Image

ROOT = r"C:\Users\kvvam\MultiModal_Code_Vulnerability_Detection"
CH_DIR = os.path.join(ROOT, "report", "chapters")
OUT_PATH = os.path.join(ROOT, "report", "Final_Report.docx")

TITLE = "AI-Based Multi-Modal Secure Code Analysis Platform"
NAME_PLACEHOLDER = "[STUDENT NAME - REQUIRES VERIFICATION]"
USN_PLACEHOLDER = "[USN NUMBER - REQUIRES VERIFICATION]"
GUIDE_PLACEHOLDER = "[GUIDE NAME AND DESIGNATION - REQUIRES VERIFICATION]"
MONTH_PLACEHOLDER = "[SUBMISSION MONTH AND YEAR - REQUIRES VERIFICATION]"
DATE_PLACEHOLDER = "[VIVA DATE - REQUIRES VERIFICATION]"

FONT_NAME = "Times New Roman"
CONTENT_WIDTH_IN = 8.27 - 1.5 - 1.0  # A4 width minus left/right margins

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def set_cell_border(cell, **kwargs):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:color'), '000000')
        tcBorders.append(el)
    tcPr.append(tcBorders)


def set_run_font(run, size=12, bold=False, italic=False, underline=False, all_caps=False, color=None):
    run.font.name = FONT_NAME
    rpr = run._element.get_or_add_rPr()
    rFonts = rpr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rpr.append(rFonts)
    rFonts.set(qn('w:ascii'), FONT_NAME)
    rFonts.set(qn('w:hAnsi'), FONT_NAME)
    rFonts.set(qn('w:cs'), FONT_NAME)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.underline = underline
    if all_caps:
        run.font.all_caps = True
    if color:
        run.font.color.rgb = RGBColor(*color)


def set_paragraph_spacing(p, line_15=True, space_after=6, alignment=None):
    pf = p.paragraph_format
    if line_15:
        pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(0)
    if alignment is not None:
        pf.alignment = alignment


def add_body_paragraph(doc, text_runs, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY):
    """text_runs: list of (text, bold, italic, code) tuples"""
    p = doc.add_paragraph()
    set_paragraph_spacing(p, alignment=alignment)
    for text, bold, italic, code in text_runs:
        r = p.add_run(text)
        set_run_font(r, size=12, bold=bold, italic=italic)
        if code:
            r.font.name = "Consolas"
            rpr = r._element.get_or_add_rPr()
            rFonts = rpr.find(qn('w:rFonts'))
            rFonts.set(qn('w:ascii'), "Consolas")
            rFonts.set(qn('w:hAnsi'), "Consolas")
    return p


INLINE_TOKEN_RE = re.compile(r'(\*\*.+?\*\*|`.+?`|\*[^*]+?\*)')


def parse_inline(text):
    """Parse **bold**, `code`, *italic* into (text, bold, italic, code) tuples."""
    runs = []
    pos = 0
    for m in INLINE_TOKEN_RE.finditer(text):
        if m.start() > pos:
            runs.append((text[pos:m.start()], False, False, False))
        tok = m.group(0)
        if tok.startswith('**'):
            runs.append((tok[2:-2], True, False, False))
        elif tok.startswith('`'):
            runs.append((tok[1:-1], False, False, True))
        elif tok.startswith('*'):
            runs.append((tok[1:-1], False, True, False))
        pos = m.end()
    if pos < len(text):
        runs.append((text[pos:], False, False, False))
    if not runs:
        runs = [(text, False, False, False)]
    return runs


def add_page_break(doc):
    doc.add_page_break()


def add_chapter_heading(doc, num, title_caps):
    """Chapter No.: 18pt Sentence case + Bold. Chapter TITLE: 18pt Capital case + Bold.
    Uses the built-in 'Heading 1' style (outline level 1) so the TOC field can find it,
    then overrides direct character formatting to match the spec's visual requirements."""
    p = doc.add_paragraph(style='Heading 1')
    set_paragraph_spacing(p, space_after=18, alignment=WD_ALIGN_PARAGRAPH.CENTER)
    r1 = p.add_run(f"Chapter {num}: ")
    set_run_font(r1, size=18, bold=True, color=(0, 0, 0))
    r2 = p.add_run(title_caps.upper())
    set_run_font(r2, size=18, bold=True, color=(0, 0, 0))
    return p


def add_first_level_heading(doc, text):
    """16pt Capital case + Bold. Uses 'Heading 2' (outline level 2) for the TOC field."""
    p = doc.add_paragraph(style='Heading 2')
    set_paragraph_spacing(p, space_after=10)
    r = p.add_run(text.upper())
    set_run_font(r, size=16, bold=True, color=(0, 0, 0))
    return p


def add_second_level_heading(doc, text):
    """14pt Sentence case (kept as authored Title Case for readability of proper nouns) + Bold.
    Uses 'Heading 3' (outline level 3) for the TOC field."""
    p = doc.add_paragraph(style='Heading 3')
    set_paragraph_spacing(p, space_after=8)
    r = p.add_run(text)
    set_run_font(r, size=14, bold=True, color=(0, 0, 0))
    return p


def add_caption(doc, text, alignment=WD_ALIGN_PARAGRAPH.CENTER):
    """12pt Sentence case + Bold"""
    p = doc.add_paragraph()
    set_paragraph_spacing(p, space_after=8, alignment=alignment, line_15=False)
    r = p.add_run(text)
    set_run_font(r, size=12, bold=True)
    return p


def add_image(doc, path, max_width_in=CONTENT_WIDTH_IN, max_height_in=4.2):
    if not os.path.exists(path):
        p = doc.add_paragraph()
        r = p.add_run(f"[MISSING IMAGE: {path}]")
        set_run_font(r, size=11, italic=True, color=(200, 0, 0))
        return
    with Image.open(path) as im:
        w_px, h_px = im.size
    aspect = h_px / w_px
    width_in = max_width_in
    height_in = width_in * aspect
    if height_in > max_height_in:
        height_in = max_height_in
        width_in = height_in / aspect
    p = doc.add_paragraph()
    set_paragraph_spacing(p, alignment=WD_ALIGN_PARAGRAPH.CENTER, line_15=False, space_after=4)
    run = p.add_run()
    run.add_picture(path, width=Inches(width_in), height=Inches(height_in))


def add_table_from_markdown(doc, header, rows):
    n_cols = len(header)
    table = doc.add_table(rows=1, cols=n_cols)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(header):
        hdr_cells[i].text = ''
        p = hdr_cells[i].paragraphs[0]
        r = p.add_run(h)
        set_run_font(r, size=11, bold=True)
        set_cell_border(hdr_cells[i])
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            if i >= n_cols:
                break
            cells[i].text = ''
            p = cells[i].paragraphs[0]
            for text, bold, italic, code in parse_inline(val):
                r = p.add_run(text)
                set_run_font(r, size=11, bold=bold, italic=italic)
            set_cell_border(cells[i])
    doc.add_paragraph().paragraph_format.space_after = Pt(6)
    return table


# ---------------------------------------------------------------------------
# Figure manifest: markdown reference path -> (figure_number, image_path)
# ---------------------------------------------------------------------------

FIGURE_IMAGES = {
    "report/figures/fig_pipeline_offline.png": os.path.join(ROOT, "report", "figures", "fig_pipeline_offline.png"),
    "report/figures/fig_architecture.png": os.path.join(ROOT, "report", "figures", "fig_architecture.png"),
    "results/model_comparison.png": os.path.join(ROOT, "results", "model_comparison.png"),
    "report/figures/confusion_matrix_xgboost.png": os.path.join(ROOT, "report", "figures", "confusion_matrix_xgboost.png"),
    "report/figures/roc_curve.png": os.path.join(ROOT, "report", "figures", "roc_curve.png"),
    "results/feature_importance.png": os.path.join(ROOT, "results", "feature_importance.png"),
    "report/figures/screenshots/fig_scanner_result.jpg": os.path.join(ROOT, "report", "figures", "screenshots", "fig_scanner_result.jpg"),
    "report/figures/screenshots/fig_analysis_view.jpg": os.path.join(ROOT, "report", "figures", "screenshots", "fig_analysis_view.jpg"),
    "report/figures/screenshots/fig_heatmap_cwe.jpg": os.path.join(ROOT, "report", "figures", "screenshots", "fig_heatmap_cwe.jpg"),
    "report/figures/screenshots/fig_recommendations_rewrite.jpg": os.path.join(ROOT, "report", "figures", "screenshots", "fig_recommendations_rewrite.jpg"),
    "report/figures/screenshots/fig_recommendations_perf.jpg": os.path.join(ROOT, "report", "figures", "screenshots", "fig_recommendations_perf.jpg"),
    "report/figures/screenshots/fig_autopatch_before_after.jpg": os.path.join(ROOT, "report", "figures", "screenshots", "fig_autopatch_before_after.jpg"),
    "report/figures/screenshots/fig_call_graph.jpg": os.path.join(ROOT, "report", "figures", "screenshots", "fig_call_graph.jpg"),
    "report/figures/screenshots/fig_cicd_run.jpg": os.path.join(ROOT, "report", "figures", "screenshots", "fig_cicd_run.jpg"),
}

FIGURE_CAPTION_RE = re.compile(r'^\*\*(Figure \d+\.\d+): (.+?)\*\*$')
TABLE_CAPTION_RE = re.compile(r'^\*\*(Table \d+\.\d+): (.+?)\*\*$')
IMG_PATH_RE = re.compile(r'`([^`]+\.(?:png|jpg|jpeg))`')


# ---------------------------------------------------------------------------
# Markdown chapter renderer
# ---------------------------------------------------------------------------

def render_markdown_chapter(doc, md_path):
    with open(md_path, encoding='utf-8') as f:
        lines = f.read().split('\n')

    i = 0
    chapter_started = False
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith('# '):
            if chapter_started:
                add_page_break(doc)
            title = stripped[2:].strip()
            m = re.match(r'CHAPTER (\d+): (.+)', title, re.IGNORECASE)
            if m:
                add_chapter_heading(doc, m.group(1), m.group(2))
            else:
                # References chapter (no "CHAPTER N" prefix)
                p = doc.add_paragraph(style='Heading 1')
                set_paragraph_spacing(p, space_after=18, alignment=WD_ALIGN_PARAGRAPH.CENTER)
                r = p.add_run(title.upper())
                set_run_font(r, size=18, bold=True, color=(0, 0, 0))
            chapter_started = True
            i += 1
            continue

        if stripped.startswith('## '):
            add_first_level_heading(doc, stripped[3:].strip())
            i += 1
            continue

        if stripped.startswith('### '):
            add_second_level_heading(doc, stripped[4:].strip())
            i += 1
            continue

        if stripped == '':
            i += 1
            continue

        # Figure caption block: **Figure X.Y: caption**  then next line(s) with `path` + description
        fm = FIGURE_CAPTION_RE.match(stripped)
        if fm:
            fig_label, fig_desc = fm.group(1), fm.group(2)
            # gather following lines until blank line (description + path)
            desc_lines = []
            j = i + 1
            while j < len(lines) and lines[j].strip() != '':
                desc_lines.append(lines[j].strip())
                j += 1
            full_desc = ' '.join(desc_lines)
            path_match = IMG_PATH_RE.search(full_desc)
            img_path = None
            if path_match:
                rel = path_match.group(1)
                img_path = FIGURE_IMAGES.get(rel)
                full_desc = IMG_PATH_RE.sub('', full_desc).strip()
                full_desc = re.sub(r'^[\s()\.]+', '', full_desc).strip()
            # image ABOVE caption, caption at BOTTOM per spec
            if img_path:
                add_image(doc, img_path)
            add_caption(doc, f"{fig_label}: {fig_desc}")
            if full_desc:
                add_body_paragraph(doc, parse_inline(full_desc), alignment=WD_ALIGN_PARAGRAPH.JUSTIFY)
            i = j
            continue

        # Table caption block: **Table X.Y: caption**
        tm = TABLE_CAPTION_RE.match(stripped)
        if tm:
            add_caption(doc, f"{tm.group(1)}: {tm.group(2)}")
            i += 1
            continue

        # Markdown table
        if stripped.startswith('|'):
            header = [c.strip() for c in stripped.strip('|').split('|')]
            i += 1
            if i < len(lines) and re.match(r'^\|[\s:-]+\|', lines[i].strip()):
                i += 1
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                rows.append(row)
                i += 1
            add_table_from_markdown(doc, header, rows)
            continue

        # Code fence
        if stripped.startswith('```'):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            p = doc.add_paragraph()
            set_paragraph_spacing(p, line_15=False, space_after=8)
            p.paragraph_format.left_indent = Inches(0.3)
            code_text = '\n'.join(code_lines)
            r = p.add_run(code_text)
            r.font.name = 'Consolas'
            r.font.size = Pt(9)
            continue

        # Bullet list (join wrapped continuation lines into the same item)
        if stripped.startswith('- ') or stripped.startswith('  - '):
            indent = len(line) - len(line.lstrip())
            item_lines = [stripped[2:].strip()]
            j = i + 1
            while j < len(lines) and lines[j].strip() != '' and not re.match(
                r'^(#|\||```|\*\*Figure|\*\*Table|-\s|\d+\.\s|---)', lines[j].strip()
            ):
                item_lines.append(lines[j].strip())
                j += 1
            full_item = ' '.join(item_lines)
            p = doc.add_paragraph(style='List Bullet')
            set_paragraph_spacing(p, space_after=4)
            if indent > 0:
                p.paragraph_format.left_indent = Inches(0.5)
            for text, bold, italic, code in parse_inline(full_item):
                r = p.add_run(text)
                set_run_font(r, size=12, bold=bold, italic=italic)
            i = j
            continue

        # Numbered list (join wrapped continuation lines into the same item)
        nm = re.match(r'^(\d+)\.\s+(.*)', stripped)
        if nm:
            item_lines = [nm.group(2)]
            j = i + 1
            while j < len(lines) and lines[j].strip() != '' and not re.match(
                r'^(#|\||```|\*\*Figure|\*\*Table|-\s|\d+\.\s|---)', lines[j].strip()
            ):
                item_lines.append(lines[j].strip())
                j += 1
            full_item = ' '.join(item_lines)
            # Rendered as a literal "N. text" paragraph (not Word's auto-numbering 'List Number'
            # style) because that style shares one numbering sequence across the whole document --
            # every independent list in later chapters/references would keep counting up instead of
            # restarting at 1. A hanging indent reproduces the visual list look without that bug.
            p = doc.add_paragraph()
            set_paragraph_spacing(p, space_after=4)
            p.paragraph_format.left_indent = Inches(0.35)
            p.paragraph_format.first_line_indent = Inches(-0.35)
            r0 = p.add_run(f"{nm.group(1)}. ")
            set_run_font(r0, size=12)
            for text, bold, italic, code in parse_inline(full_item):
                r = p.add_run(text)
                set_run_font(r, size=12, bold=bold, italic=italic)
            i = j
            continue

        # Blockquote / horizontal rule
        if stripped == '---':
            i += 1
            continue

        # Standalone bold line (e.g. emphasis headers not matching figure/table)
        # Regular paragraph (join wrapped lines until blank)
        para_lines = [stripped]
        j = i + 1
        while j < len(lines) and lines[j].strip() != '' and not re.match(
            r'^(#|\||```|\*\*Figure|\*\*Table|- |\d+\.\s|---)', lines[j].strip()
        ):
            para_lines.append(lines[j].strip())
            j += 1
        full_text = ' '.join(para_lines)
        add_body_paragraph(doc, parse_inline(full_text))
        i = j

    return doc


print("Module loaded OK")
