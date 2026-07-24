
# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_report import (
    Document, Pt, Inches, RGBColor, WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_SECTION,
    qn, OxmlElement, set_run_font, set_paragraph_spacing, add_body_paragraph, parse_inline,
    add_page_break, add_chapter_heading, add_first_level_heading, add_second_level_heading,
    add_caption, add_image, add_table_from_markdown, render_markdown_chapter,
    TITLE, NAME_PLACEHOLDER, USN_PLACEHOLDER, GUIDE_PLACEHOLDER, MONTH_PLACEHOLDER, DATE_PLACEHOLDER,
    FONT_NAME, ROOT, CH_DIR, OUT_PATH,
)
import os

MARGIN_TOP = Inches(1.0)
MARGIN_BOTTOM = Inches(1.0)
MARGIN_LEFT = Inches(1.5)
MARGIN_RIGHT = Inches(1.0)
PAGE_W = Inches(8.27)
PAGE_H = Inches(11.69)


def set_section_page_setup(section):
    section.page_width = PAGE_W
    section.page_height = PAGE_H
    section.top_margin = MARGIN_TOP
    section.bottom_margin = MARGIN_BOTTOM
    section.left_margin = MARGIN_LEFT
    section.right_margin = MARGIN_RIGHT
    section.header_distance = Inches(0.5)
    section.footer_distance = Inches(0.5)


def set_page_number_format(section, fmt, restart_at=None):
    """fmt: 'lowerRoman' or 'decimal'"""
    sectPr = section._sectPr
    pgNumType = sectPr.find(qn('w:pgNumType'))
    if pgNumType is None:
        pgNumType = OxmlElement('w:pgNumType')
        sectPr.append(pgNumType)
    pgNumType.set(qn('w:fmt'), fmt)
    if restart_at is not None:
        pgNumType.set(qn('w:start'), str(restart_at))


def add_page_number_footer(section, align=WD_ALIGN_PARAGRAPH.RIGHT):
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.text = ''
    p.alignment = align
    run = p.add_run()
    set_run_font(run, size=12)
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = 'PAGE'
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'end')
    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)


def insert_toc_field(doc):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, line_15=False)
    run = p.add_run()
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    fldChar1.set(qn('w:dirty'), 'true')
    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = 'TOC \\o "1-3" \\h \\z \\u'
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'separate')
    t = OxmlElement('w:t')
    t.text = "Right-click here and choose ‘Update Field’ in Microsoft Word to generate the Table of Contents with page numbers."
    fldChar3 = OxmlElement('w:fldChar')
    fldChar3.set(qn('w:fldCharType'), 'end')
    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)
    run._r.append(t)
    run._r.append(fldChar3)
    set_run_font(run, size=12)


def centered(doc, text, size=12, bold=False, italic=False, space_after=0, all_caps=False):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=space_after)
    r = p.add_run(text.upper() if all_caps else text)
    set_run_font(r, size=size, bold=bold, italic=italic)
    return p


def blank(doc, n=1):
    for _ in range(n):
        doc.add_paragraph()


# ---------------------------------------------------------------------------
doc = Document()

# Set base Normal style
normal = doc.styles['Normal']
normal.font.name = FONT_NAME
normal.font.size = Pt(12)
rpr = normal.element.get_or_add_rPr()
rFonts = rpr.find(qn('w:rFonts'))
if rFonts is None:
    rFonts = OxmlElement('w:rFonts')
    rpr.append(rFonts)
rFonts.set(qn('w:ascii'), FONT_NAME)
rFonts.set(qn('w:hAnsi'), FONT_NAME)
rFonts.set(qn('w:cs'), FONT_NAME)

section0 = doc.sections[0]
set_section_page_setup(section0)

# =========================== COVER PAGE ===========================
blank(doc, 2)
centered(doc, "DAYANANDA SAGAR UNIVERSITY", size=16, bold=True, space_after=4)
centered(doc, "Kudlu Gate, Hosur Road, Bengaluru – 560068", size=14, bold=True, space_after=20)
centered(doc, "SCHOOL OF COMPUTER APPLICATIONS", size=16, bold=True, space_after=30)
centered(doc, "A Project Report on", size=16, space_after=6)
centered(doc, TITLE, size=14, bold=True, space_after=24)
centered(doc, "Submitted in Partial fulfilment of the requirements for the award of the Degree of", size=14, space_after=6)
centered(doc, "MASTER OF COMPUTER APPLICATIONS", size=16, bold=True, space_after=24)
centered(doc, "Submitted by", size=16, space_after=6)
centered(doc, NAME_PLACEHOLDER, size=14, bold=True, space_after=2)
centered(doc, USN_PLACEHOLDER, size=14, bold=True, space_after=24)
centered(doc, "Under the guidance of", size=16, space_after=6)
centered(doc, GUIDE_PLACEHOLDER, size=16, space_after=24)
centered(doc, MONTH_PLACEHOLDER, size=14, space_after=24)
centered(doc, "DAYANANDA SAGAR UNIVERSITY", size=14, bold=True, space_after=2)
centered(doc, "Kudlu Gate, Hosur Road, Bengaluru – 560068", size=14, space_after=0)

# =========================== SECTION BREAK: front matter, roman numerals ===========================
sec_front = doc.add_section(WD_SECTION.NEW_PAGE)
set_section_page_setup(sec_front)
set_page_number_format(sec_front, 'lowerRoman', restart_at=1)
add_page_number_footer(sec_front)

# --- Bonafide Certificate ---
centered(doc, "SCHOOL OF COMPUTER APPLICATIONS", size=16, bold=True, space_after=4)
centered(doc, "BONAFIDE CERTIFICATE", size=16, bold=True, space_after=20)
add_body_paragraph(doc, parse_inline(
    f"This is to certify that the project titled ‘{TITLE}’ is a bonafide record of the work "
    f"undertaken by {NAME_PLACEHOLDER} ({USN_PLACEHOLDER}) in partial fulfillment of the requirements "
    f"for the award of the Master of Computer Applications degree at the School of Computer "
    f"Applications, Dayananda Sagar University, Bengaluru, during the academic year 2025-2026."
))
blank(doc, 2)
p = doc.add_paragraph()
set_paragraph_spacing(p, line_15=False)
r = p.add_run("GUIDE" + " " * 40 + "DEAN")
set_run_font(r, size=12, bold=True)
blank(doc, 2)
p = doc.add_paragraph()
set_paragraph_spacing(p, line_15=False)
r = p.add_run("Internal Examiner" + " " * 30 + "External Examiner")
set_run_font(r, size=12, bold=True)
add_page_break(doc)

# --- Declaration ---
centered(doc, "SCHOOL OF COMPUTER APPLICATIONS", size=16, bold=True, space_after=4)
centered(doc, "DECLARATION", size=16, bold=True, space_after=20)
add_body_paragraph(doc, parse_inline(
    f"I, {NAME_PLACEHOLDER}, a student of the Master of Computer Applications program at the School of "
    f"Computer Applications, Dayananda Sagar University, hereby declare that this project, titled "
    f"‘{TITLE}’, is the result of my independent work carried out under the supervision of "
    f"{GUIDE_PLACEHOLDER}."
))
add_body_paragraph(doc, parse_inline(
    "I am submitting this project work in partial fulfillment of the requirements for the award of the "
    "Master of Computer Applications degree by Dayananda Sagar University, Bengaluru, for the Academic "
    "Year 2025-2026."
))
add_body_paragraph(doc, parse_inline(
    "I further affirm that this project report, in whole or in part, has not been submitted for the "
    "award of any other degree or diploma at this or any other university/institution."
))
add_body_paragraph(doc, parse_inline("Signed by me on: " + DATE_PLACEHOLDER), alignment=WD_ALIGN_PARAGRAPH.LEFT)
add_body_paragraph(doc, parse_inline("**Signature of the Candidate**"), alignment=WD_ALIGN_PARAGRAPH.LEFT)
blank(doc, 1)
add_body_paragraph(doc, parse_inline(
    f"This is to certify that the project work submitted by {NAME_PLACEHOLDER} has been carried out "
    f"under my guidance, and the declaration made by the candidate is true to the best of my knowledge."
))
add_body_paragraph(doc, parse_inline("**Signature of the Guide**"), alignment=WD_ALIGN_PARAGRAPH.LEFT)
add_body_paragraph(doc, parse_inline("Date: " + DATE_PLACEHOLDER), alignment=WD_ALIGN_PARAGRAPH.LEFT)
add_page_break(doc)

# --- Acknowledgement ---
centered(doc, "ACKNOWLEDGEMENT", size=16, bold=True, space_after=20)
ack_paras = [
    "I express my heartfelt gratitude and salutations to my beloved and highly esteemed institute, "
    "Dayananda Sagar University, for providing me with an excellent platform to learn and grow. I am "
    "deeply thankful for the unwavering support and encouragement extended throughout my academic "
    "journey.",
    "I extend my sincere gratitude to Dr. D. Hemachandra Sagar, Chancellor, and Dr. Premachandra Sagar, "
    "Pro Chancellor, Dayananda Sagar University, for their visionary leadership and continuous support "
    "in fostering an environment of academic excellence and innovation.",
    "I am profoundly grateful to Dr. B.S. Satyanarayana, Vice Chancellor, and Dr. Puttamadappa C, "
    "Registrar, Dayananda Sagar University, for their invaluable guidance and commitment to ensuring a "
    "world-class education at the university.",
    "I extend my heartfelt thanks to Dr. S. Senthil, Professor and Dean, School of Computer "
    "Applications, Dayananda Sagar University, for his valuable suggestions, expert advice, and constant "
    "support throughout my project.",
    f"I am deeply indebted to my guide, {GUIDE_PLACEHOLDER}, School of Computer Applications, for the "
    f"continuous support, necessary advice, and invaluable guidance that played a significant role in "
    f"shaping the outcome of my project.",
    "I would also like to extend my appreciation to all the teaching and non-teaching staff members of "
    "the School of Computer Applications for their support and assistance during my academic tenure.",
    "Lastly, I am forever grateful to my parents and friends, whose unwavering support, motivation, and "
    "encouragement have been my strength throughout this journey.",
]
for para in ack_paras:
    add_body_paragraph(doc, parse_inline(para))
blank(doc, 1)
add_body_paragraph(doc, parse_inline(NAME_PLACEHOLDER), alignment=WD_ALIGN_PARAGRAPH.LEFT)
add_body_paragraph(doc, parse_inline(USN_PLACEHOLDER), alignment=WD_ALIGN_PARAGRAPH.LEFT)
add_page_break(doc)

# --- Contents ---
centered(doc, "CONTENTS", size=16, bold=True, space_after=20)
insert_toc_field(doc)

# =========================== SECTION BREAK: main body, arabic numerals ===========================
sec_body = doc.add_section(WD_SECTION.NEW_PAGE)
set_section_page_setup(sec_body)
set_page_number_format(sec_body, 'decimal', restart_at=1)
add_page_number_footer(sec_body)

CHAPTER_FILES = [
    "ch1_introduction.md",
    "ch2_literature.md",
    "ch3_methodology.md",
    "ch4_design.md",
    "ch5_implementation.md",
    "ch6_testing.md",
    "ch7_results.md",
    "ch8_conclusion.md",
    "references.md",
]

first = True
for fname in CHAPTER_FILES:
    path = os.path.join(CH_DIR, fname)
    if not first:
        add_page_break(doc)
    first = False
    render_markdown_chapter(doc, path)

doc.save(OUT_PATH)
print("Saved:", OUT_PATH)
