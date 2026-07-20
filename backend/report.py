# =============================================================================
# report.py -- Security Report (PDF) generation via ReportLab.
# Builds a professional PDF for either a single scan or a whole batch/project.
# =============================================================================

import io
import datetime as dt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.piecharts import Pie

INK = colors.HexColor("#0b0b0b")
MUTED = colors.HexColor("#52514e")
ACCENT = colors.HexColor("#2a78d6")
GOOD = colors.HexColor("#0ca30c")
WARNING = colors.HexColor("#c98500")
SERIOUS = colors.HexColor("#eb6834")
CRITICAL = colors.HexColor("#d03b3b")

RISK_COLOR_MAP = {
    "SAFE": GOOD, "LOW RISK": colors.HexColor("#1baf7a"),
    "MEDIUM RISK": WARNING, "HIGH RISK": SERIOUS, "CRITICAL": CRITICAL,
}


def _grade(safety_score: float) -> str:
    if safety_score >= 90:
        return "A"
    if safety_score >= 80:
        return "B"
    if safety_score >= 70:
        return "C"
    if safety_score >= 60:
        return "D"
    return "F"


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("H1", parent=ss["Heading1"], textColor=INK, fontSize=22, spaceAfter=4))
    ss.add(ParagraphStyle("H2", parent=ss["Heading2"], textColor=ACCENT, fontSize=13, spaceBefore=14, spaceAfter=6))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], textColor=INK, fontSize=9.5, leading=13))
    ss.add(ParagraphStyle("Muted", parent=ss["Normal"], textColor=MUTED, fontSize=9))
    ss.add(ParagraphStyle("Grade", parent=ss["Heading1"], fontSize=40, alignment=1))
    return ss


def _header(elements, ss, title, project_name):
    elements.append(Paragraph("AI Secure Code Analysis Platform", ss["Muted"]))
    elements.append(Paragraph(title, ss["H1"]))
    elements.append(Paragraph(f"Project: <b>{project_name}</b>", ss["Body"]))
    elements.append(Paragraph(
        f"Generated: {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ss["Muted"],
    ))
    elements.append(Spacer(1, 10))


def _grade_block(elements, ss, safety_score, grade):
    color = GOOD if grade in ("A", "B") else (WARNING if grade == "C" else CRITICAL)
    d = Drawing(120, 120)
    d.add(Rect(10, 10, 100, 100, rx=12, ry=12, fillColor=color, strokeColor=None))
    d.add(String(60, 45, grade, fontSize=48, fillColor=colors.white, textAnchor="middle"))
    tbl = Table([[d, Paragraph(
        f"<b>Overall Security Grade: {grade}</b><br/>Safety score: {safety_score:.1f} / 100",
        ss["Body"],
    )]], colWidths=[130, 350])
    tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    elements.append(tbl)
    elements.append(Spacer(1, 10))


def _stats_table(elements, ss, rows):
    data = [[Paragraph(f"<b>{k}</b>", ss["Muted"]), Paragraph(str(v), ss["Body"])] for k, v in rows]
    tbl = Table(data, colWidths=[220, 260])
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e1e0d9")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f9f9f7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(tbl)


def _recommendations_block(elements, ss, panels):
    if not panels:
        return
    elements.append(Paragraph("Recommendations", ss["H2"]))
    for panel in panels:
        elements.append(Paragraph(f"<b>{panel['title']}</b>", ss["Body"]))
        for tip in panel.get("tips", []):
            elements.append(Paragraph(f"&bull; {tip}", ss["Body"]))
        elements.append(Spacer(1, 4))


def build_single_scan_pdf(scan: dict, line_risks: list, recs: list) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=18 * mm)
    ss = _styles()
    elements = []

    _header(elements, ss, "Security Scan Report", scan.get("project_name", "Untitled Project"))

    safety_score = max(0.0, 100.0 - scan["vuln_probability"])
    grade = _grade(safety_score)
    _grade_block(elements, ss, safety_score, grade)

    elements.append(Paragraph("Scan Summary", ss["H2"]))
    _stats_table(elements, ss, [
        ("File", scan.get("filename", "-")),
        ("Verdict", scan["verdict"]),
        ("Risk Level", scan["risk_level"]),
        ("Vulnerability Probability", f"{scan['vuln_probability']:.2f}%"),
        ("Model Confidence", f"{scan['confidence']:.2f}%"),
        ("Model Used", scan["model_used"]),
        ("Lines of Code", scan.get("loc", "-")),
    ])
    elements.append(Spacer(1, 8))

    if line_risks:
        elements.append(Paragraph("Detected Issues by Line", ss["H2"]))
        data = [["Line", "Severity", "CWE", "Reason"]]
        for lr in line_risks[:40]:
            data.append([
                str(lr["line"]),
                str(lr["severity"]),
                ", ".join(lr["cwe"]) or "-",
                "; ".join(lr["reasons"])[:90],
            ])
        tbl = Table(data, colWidths=[35, 45, 70, 330], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e1e0d9")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a19")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 8))

    _recommendations_block(elements, ss, recs)

    doc.build(elements)
    return buf.getvalue()


def build_batch_pdf(batch_summary: dict, results: list, project_name: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=18 * mm)
    ss = _styles()
    elements = []

    _header(elements, ss, "Project Security Report", project_name)

    total = batch_summary["total_files_scanned"]
    vulnerable = batch_summary["vulnerable_count"]
    pct_vuln = (vulnerable / total * 100) if total else 0
    safety_score = max(0.0, 100.0 - pct_vuln)
    grade = _grade(safety_score)
    _grade_block(elements, ss, safety_score, grade)

    elements.append(Paragraph("Project Summary", ss["H2"]))
    _stats_table(elements, ss, [
        ("Files Scanned", total),
        ("Vulnerable Files", vulnerable),
        ("Safe Files", batch_summary["safe_count"]),
        ("Vulnerability Rate", f"{pct_vuln:.1f}%"),
    ])
    elements.append(Spacer(1, 10))

    if total:
        d = Drawing(220, 160)
        pie = Pie()
        pie.x, pie.y = 40, 15
        pie.width = pie.height = 130
        pie.data = [vulnerable, batch_summary["safe_count"]]
        pie.labels = [f"Vulnerable ({vulnerable})", f"Safe ({batch_summary['safe_count']})"]
        pie.slices[0].fillColor = CRITICAL
        pie.slices[1].fillColor = GOOD
        d.add(pie)
        elements.append(d)
        elements.append(Spacer(1, 6))

    elements.append(Paragraph("Files Requiring Review", ss["H2"]))
    flagged = [r for r in results if r["verdict"] == "VULNERABLE"]
    flagged.sort(key=lambda r: -r["vuln_probability"])
    if flagged:
        data = [["File", "Risk Level", "Probability", "Confidence"]]
        for r in flagged[:60]:
            data.append([
                r["filename"], r["risk_level"], f"{r['vuln_probability']:.1f}%", f"{r['confidence']:.1f}%",
            ])
        tbl = Table(data, colWidths=[220, 100, 80, 80], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e1e0d9")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a19")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ]))
        elements.append(tbl)
    else:
        elements.append(Paragraph("No vulnerable files detected in this batch.", ss["Body"]))

    doc.build(elements)
    return buf.getvalue()
