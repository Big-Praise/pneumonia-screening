"""Build the per-scan PDF report (reportlab). No Streamlit here — pure inputs -> bytes.

Decisions:
- The report reflects the SAVED scan record (label, confidence, threshold_used),
  never an unsaved slider position, so the PDF always matches the database.
- The disclaimer is drawn in the footer of EVERY page, not just once.
- Only reportlab's built-in fonts are used (no font files to ship). Their
  character set lacks symbols like ">=" as one glyph or "x" multiplication
  signs, so text below sticks to plain ASCII-ish punctuation.
- Images are passed in already rendered (Grad-CAM/LIME overlays), so the PDF
  shows exactly what the app shows.
"""
import io
import textwrap
from dataclasses import dataclass
from datetime import datetime

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

TEAL = colors.HexColor("#0f766e")
AMBER = colors.HexColor("#b45309")
INK = colors.HexColor("#12302c")
MUTED = colors.HexColor("#4b6460")
DISCLAIMER_BG = colors.HexColor("#fff8e6")

DISCLAIMER = (
    "Decision-support only - not a diagnosis. This report gives a screening result from a "
    "machine-learning model. It can miss cases and over-flag normal X-rays. A qualified "
    "clinician must make the final decision."
)
LIMITATIONS = [
    "The model can miss pneumonia and can over-flag normal X-rays.",
    "Training data was likely pediatric and single-source; performance on other "
    "populations or scanners is unknown.",
    "The threshold changes how the probability is labelled, not the model itself.",
    "Grad-CAM is computed on a coarse 7 by 7 grid: it shows broad regions, not lesion "
    "boundaries. Highlights outside the lungs suggest the model may be using "
    "non-clinical cues.",
]


@dataclass
class ReportData:
    scan_id: int
    scan_time: datetime          # local time, already converted by the caller
    patient_name: str
    patient_age: int | None
    patient_sex: str | None
    clinician: str
    label: str                   # saved predicted_label
    confidence: float            # saved confidence
    pneumonia_prob: float
    threshold: float             # saved threshold_used
    model_source: str
    is_demo: bool
    original: Image.Image
    gradcam: Image.Image | None
    lime: Image.Image | None
    lime_weak: bool = False
    agreement: float | None = None


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], textColor=TEAL, fontSize=18,
                                alignment=0, spaceAfter=2),
        "sub": ParagraphStyle("s", parent=ss["Normal"], textColor=MUTED, fontSize=9),
        "h": ParagraphStyle("h", parent=ss["Heading3"], textColor=INK, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("b", parent=ss["Normal"], textColor=INK, fontSize=9.5, leading=13),
        "small": ParagraphStyle("sm", parent=ss["Normal"], textColor=MUTED, fontSize=8, leading=10.5),
        "caption": ParagraphStyle("c", parent=ss["Normal"], textColor=MUTED, fontSize=8,
                                  alignment=1, leading=10),
        "result": ParagraphStyle("r", parent=ss["Normal"], fontSize=15, leading=19,
                                 fontName="Helvetica-Bold"),
        "banner": ParagraphStyle("bn", parent=ss["Normal"], fontSize=9, leading=12,
                                 textColor=colors.HexColor("#4a3a12")),
    }


def _rl_image(img: Image.Image, width: float) -> RLImage:
    """PIL -> reportlab flowable at a fixed width, aspect preserved."""
    buf = io.BytesIO()
    # JPEG q90: visually identical at print size, ~7x smaller than PNG (easier to email).
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    buf.seek(0)
    w, h = img.size
    return RLImage(buf, width=width, height=width * h / w)


def _boxed(par: Paragraph, bg, border) -> Table:
    t = Table([[par]], colWidths=[180 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.8, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def build_pdf(d: ReportData) -> bytes:
    st = _styles()
    generated = datetime.now().astimezone().strftime("%d %b %Y, %H:%M")
    buf = io.BytesIO()

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        # Disclaimer on every page (GUARDRAILS).
        text = canvas.beginText(15 * mm, 14 * mm)
        for line in textwrap.wrap(DISCLAIMER, 120):
            text.textLine(line)
        canvas.drawText(text)
        canvas.drawRightString(195 * mm, 8 * mm,
                               f"Scan #{d.scan_id} - generated {generated} - page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=14 * mm, bottomMargin=24 * mm,
                            title=f"Screening report - scan {d.scan_id}",
                            author="Pneumonia Screening (decision-support)")
    story = [
        Paragraph("Chest X-ray Screening Report", st["title"]),
        Paragraph("Decision-support tool - screening result, not a diagnosis", st["sub"]),
        Spacer(1, 6),
        _boxed(Paragraph(DISCLAIMER, st["banner"]), DISCLAIMER_BG, colors.HexColor("#d99a1e")),
    ]
    if d.is_demo:
        story += [Spacer(1, 4), _boxed(Paragraph(
            "<b>DEMO MODE</b> - no trained model was loaded. This result comes from a mock "
            "predictor and means nothing clinically.", st["banner"]),
            colors.HexColor("#eef2ff"), colors.HexColor("#4f46e5"))]

    # --- details
    facts = [
        ["Patient", d.patient_name, "Scan date", d.scan_time.strftime("%d %b %Y, %H:%M")],
        ["Age / sex", f"{d.patient_age if d.patient_age is not None else '-'} / {d.patient_sex or '-'}",
         "Screened by", d.clinician],
        ["Scan ID", f"#{d.scan_id}", "Model", d.model_source],
    ]
    t = Table(facts, colWidths=[24 * mm, 66 * mm, 24 * mm, 66 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9), ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#d5e3e0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [Paragraph("Details", st["h"]), t]

    # --- result
    is_pn = d.label == "PNEUMONIA"
    colour = AMBER if is_pn else TEAL
    headline = "Findings suggest pneumonia" if is_pn else "No pneumonia pattern detected"
    story += [
        Paragraph("Screening result", st["h"]),
        Paragraph(f'<font color="{colour.hexval()}">{headline}</font>', st["result"]),
        Paragraph(
            f"Screening result: likely <b>{d.label}</b> with <b>{d.confidence:.0%}</b> "
            f"confidence. Model pneumonia probability p = {d.pneumonia_prob:.3f}; threshold "
            f"used = {d.threshold:.2f} (PNEUMONIA when p is at or above the threshold).",
            st["body"]),
    ]
    if d.confidence < 0.5:
        story.append(Paragraph(
            "Note: the model itself leans the other way; this label comes from the "
            "chosen threshold. Treat as borderline.", st["body"]))

    # --- images
    col_w = 57 * mm
    cells = [_rl_image(d.original, col_w)]
    caps = ["Original X-ray"]
    if d.gradcam is not None:
        cells.append(_rl_image(d.gradcam, col_w))
        caps.append(f"Grad-CAM for {d.label} (red = strongest)")
    else:
        cells.append(Paragraph("Grad-CAM unavailable", st["caption"]))
        caps.append("")
    if d.lime is not None:
        cells.append(_rl_image(d.lime, col_w))
        caps.append(f"LIME for {d.label} (green = top regions)")
    else:
        cells.append(Paragraph("LIME was not run for this scan.", st["caption"]))
        caps.append("")
    grid = Table([cells, [Paragraph(c, st["caption"]) for c in caps]],
                 colWidths=[60 * mm] * 3)
    grid.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                              ("VALIGN", (0, 0), (-1, 0), "MIDDLE")]))
    expl = ["Grad-CAM and LIME are two independent explanation methods; agreement "
            "increases confidence in the highlighted region."]
    if d.agreement is not None:
        word = "high" if d.agreement >= 0.5 else "partial" if d.agreement >= 0.2 else "low"
        expl.append(f"Agreement between the two: {word} ({d.agreement:.0%} of LIME's regions "
                    "fall in Grad-CAM's hottest area).")
    if d.lime_weak:
        expl.append("LIME evidence is weak: hiding any single region barely changes the "
                    "prediction.")
    story.append(KeepTogether([Paragraph("What drove this result", st["h"]), grid,
                               Spacer(1, 4), Paragraph(" ".join(expl), st["body"])]))

    # --- limitations
    story += [Paragraph("Known limitations", st["h"])]
    story += [Paragraph(f"- {item}", st["body"]) for item in LIMITATIONS]

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def filename(scan_id: int, scan_time: datetime) -> str:
    """No patient name in the filename — downloads folders and email subjects leak."""
    return f"screening_report_scan{scan_id}_{scan_time.strftime('%Y%m%d')}.pdf"
