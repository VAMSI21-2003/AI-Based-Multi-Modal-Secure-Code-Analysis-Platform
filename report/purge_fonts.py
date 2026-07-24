
# -*- coding: utf-8 -*-
"""Standalone re-runnable pass: strips any theme font references (Cambria/
Calibri via asciiTheme/hAnsiTheme/cstheme) that Word's own COM automation can
reintroduce when it populates the TOC field, since that step runs after
assemble_docx.py's own purge. Usage: python report/purge_fonts.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_report import ROOT
import importlib.util
spec = importlib.util.spec_from_file_location("assemble_helpers", os.path.join(ROOT, "report", "assemble_docx.py"))
# assemble_docx.py runs the whole build on import, so we don't import it directly --
# instead duplicate the tiny purge function here to keep this script side-effect-free.
import zipfile, shutil, re as _re

OUT_PATH = os.path.join(ROOT, "report", "Final_Report.docx")


def purge_theme_fonts_from_docx(path):
    tmp_path = path + '.tmp'
    with zipfile.ZipFile(path, 'r') as zin:
        names = zin.namelist()
        contents = {n: zin.read(n) for n in names}

    theme_attr_re = _re.compile(
        rb'\s(?:w:asciiTheme|w:hAnsiTheme|w:cstheme|w:eastAsiaTheme)="[^"]*"')

    def fix_xml_bytes(data):
        text = data.decode('utf-8')

        def fix_rfonts(m):
            tag = m.group(0)
            if 'asciiTheme' in tag or 'hAnsiTheme' in tag or 'cstheme' in tag or 'eastAsiaTheme' in tag:
                tag = theme_attr_re.sub(b'', tag.encode('utf-8')).decode('utf-8')
                if 'w:ascii="' not in tag:
                    tag = tag.replace('<w:rFonts', '<w:rFonts w:ascii="Times New Roman" '
                                                    'w:hAnsi="Times New Roman" w:cs="Times New Roman"')
            return tag
        text = _re.sub(r'<w:rFonts\b[^/]*/>', fix_rfonts, text)
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
                print(f"  purged theme fonts from {n}")
            contents[n] = after
    for n in names:
        if n.startswith('word/header') or n.startswith('word/footer'):
            contents[n] = fix_xml_bytes(contents[n])

    with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(n, contents[n])
    shutil.move(tmp_path, path)
    print(f"Done. {changed} XML part(s) modified.")


if __name__ == "__main__":
    purge_theme_fonts_from_docx(OUT_PATH)
