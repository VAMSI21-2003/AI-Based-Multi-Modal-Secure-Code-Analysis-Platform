
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


def force_style_font(doc, style_name, font_name=FONT_NAME, size=None, bold=None,
                      base_on_style=None, style_type=None):
    """Explicitly sets font on a style's rPr, stripping any asciiTheme/hAnsiTheme/
    cstheme/eastAsiaTheme attributes so the theme's Cambria/Calibri can never show
    through. Creates the style (based on Normal) if it doesn't exist yet -- this
    matters for TOC 1/2/3, which Word would otherwise invent from its own Calibri
    based latent style the first time the TOC field is populated."""
    from docx.enum.style import WD_STYLE_TYPE
    try:
        style = doc.styles[style_name]
    except KeyError:
        style = doc.styles.add_style(style_name, style_type or WD_STYLE_TYPE.PARAGRAPH)
        if base_on_style:
            style.base_style = doc.styles[base_on_style]
    style.font.name = font_name
    if size:
        style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    rpr = style.element.get_or_add_rPr()
    rFonts = rpr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rpr.append(rFonts)
    for theme_attr in ('w:asciiTheme', 'w:hAnsiTheme', 'w:cstheme', 'w:eastAsiaTheme'):
        key = qn(theme_attr)
        if rFonts.get(key) is not None:
            del rFonts.attrib[key]
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rFonts.set(qn('w:cs'), font_name)
    return style


def force_all_style_fonts(doc):
    """Every built-in style python-docx's default template ships with a Cambria
    (majorHAnsi theme) or Calibri (minorHAnsi theme) font baked in, independent of
    any direct run-level formatting applied on top. Heading styles use Cambria;
    Normal/List/TOC styles use Calibri. Both must be overridden at the STYLE level,
    not just on individual runs, or pdffonts will keep finding them wherever a
    paragraph/run doesn't carry a full direct override (e.g. Word's own
    auto-generated TOC entry text)."""
    for name in ['Normal', 'Title', 'Subtitle', 'Heading 1', 'Heading 2', 'Heading 3',
                 'Heading 4', 'Heading 5', 'List Bullet', 'List Number', 'List Paragraph',
                 'Caption', 'Quote', 'Intense Quote', 'Strong', 'Emphasis', 'Hyperlink',
                 'Default Paragraph Font', 'Header', 'Footer', 'Table Grid',
                 'No Spacing']:
        force_style_font(doc, name)
    # TOC 1-3: pre-create with Times New Roman BEFORE Word ever populates the TOC
    # field, so Word reuses these definitions instead of inventing Calibri ones.
    for name in ['TOC 1', 'TOC 2', 'TOC 3']:
        force_style_font(doc, name, base_on_style='Normal')


def purge_theme_fonts_from_docx(path):
    """Belt-and-suspenders post-process: after Word's own COM automation updates
    the TOC field (which can (re)introduce asciiTheme='minorHAnsi' on the
    generated entry runs even when the TOC 1/2/3 styles were pre-defined), strip
    every remaining theme font reference directly from the saved .docx XML and
    replace literal Cambria/Calibri typeface names with Times New Roman, so no
    code path can leave a non-Times-New-Roman font in the final file."""
    import zipfile, shutil, re as _re
    tmp_path = path + '.tmp'
    with zipfile.ZipFile(path, 'r') as zin:
        names = zin.namelist()
        contents = {n: zin.read(n) for n in names}

    theme_attr_re = _re.compile(
        rb'\s(?:w:asciiTheme|w:hAnsiTheme|w:cstheme|w:eastAsiaTheme)="[^"]*"')

    def fix_xml_bytes(data):
        text = data.decode('utf-8')
        # Any <w:rFonts .../> that had a theme attribute needs an explicit
        # Times New Roman fallback if it doesn't already carry a literal ascii/hAnsi.
        def fix_rfonts(m):
            tag = m.group(0)
            if 'asciiTheme' in tag or 'hAnsiTheme' in tag or 'cstheme' in tag or 'eastAsiaTheme' in tag:
                tag = theme_attr_re.sub(b'', tag.encode('utf-8')).decode('utf-8')
                if 'w:ascii="' not in tag:
                    tag = tag.replace('<w:rFonts', '<w:rFonts w:ascii="Times New Roman" '
                                                    'w:hAnsi="Times New Roman" w:cs="Times New Roman"')
            return tag
        text = _re.sub(r'<w:rFonts\b[^/]*/>', fix_rfonts, text)
        # Literal theme-font typeface names that might remain anywhere else (e.g. theme1.xml)
        for bad in ('Cambria', 'Calibri Light', 'Calibri-Bold', 'Calibri'):
            text = text.replace(f'typeface="{bad}"', 'typeface="Times New Roman"')
        return text.encode('utf-8')

    changed = 0
    for n in ['word/styles.xml', 'word/document.xml', 'word/theme/theme1.xml']:
        if n in contents:
            before = contents[n]
            after = fix_xml_bytes(before)
            if after != before:
                changed += 1
            contents[n] = after
    for n in names:
        if n.startswith('word/header') or n.startswith('word/footer'):
            contents[n] = fix_xml_bytes(contents[n])

    with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(n, contents[n])
    shutil.move(tmp_path, path)
    print(f"purge_theme_fonts_from_docx: rewrote {changed} XML part(s) with theme font references")


def add_page_border(section):
    """Matches report/MCA_4sem_Project_Report_format.docx's own page border exactly
    (read directly from its word/document.xml): single black rule, 3pt weight
    (sz=24 eighths-of-a-point), 24pt offset from the page edge on all 4 sides.
    Must be called on EVERY section -- python-docx sections do not share sectPr,
    so a border added to only one section would appear on some pages and not
    others."""
    sectPr = section._sectPr
    existing = sectPr.find(qn('w:pgBorders'))
    if existing is not None:
        sectPr.remove(existing)
    pgBorders = OxmlElement('w:pgBorders')
    pgBorders.set(qn('w:offsetFrom'), 'page')
    for edge in ('top', 'left', 'bottom', 'right'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '24')
        el.set(qn('w:space'), '24')
        el.set(qn('w:color'), '000000')
        pgBorders.append(el)
    # OOXML CT_SectPr schema order: pgSz, pgMar, ..., pgBorders, ..., pgNumType, cols, ...
    # pgBorders must be inserted right after pgMar (and before pgNumType/cols) or
    # Word will silently reject/ignore the element on load.
    pgMar = sectPr.find(qn('w:pgMar'))
    if pgMar is not None:
        pgMar.addnext(pgBorders)
    else:
        sectPr.insert(0, pgBorders)


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

# Force Times New Roman at the STYLE level (Normal, every Heading, Title, TOC 1-3,
# List styles, etc.) -- not just on individual runs -- since python-docx's default
# template bakes in Cambria (headings) / Calibri (Normal, lists, TOC) via theme
# font references that survive independently of direct run formatting.
force_all_style_fonts(doc)
normal = doc.styles['Normal']
normal.font.size = Pt(12)

section0 = doc.sections[0]
set_section_page_setup(section0)
add_page_border(section0)

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
add_page_border(sec_front)
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
add_page_border(sec_body)
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
purge_theme_fonts_from_docx(OUT_PATH)
print("Saved:", OUT_PATH)
