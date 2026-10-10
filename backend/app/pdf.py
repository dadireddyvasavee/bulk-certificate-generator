from html import escape
from pathlib import Path
import os
import uuid
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(
    TTFont("CertificateSans", str(Path(__file__).parent / "assets" / "DejaVuSans.ttf"))
)

# Professional palette: deep navy ink, muted gold accents, soft grey labels.
INK = "#1A2B4A"
GOLD = "#B08D4C"
MUTED = "#6B7280"
INK_RGB = (0.102, 0.169, 0.290)
GOLD_RGB = (0.690, 0.553, 0.298)
FAINT_RGB = (0.820, 0.835, 0.859)


# Paragraph wraps long words; fixed vertical slots shrink typography to fit.
def generate(path: Path, job, name: str, certificate_id: str) -> None:
    supported = pdfmetrics.getFont("CertificateSans").face.charToGlyph
    for value in (job.organization, job.title, job.statement, job.event, job.signatory, name):
        if any(ord(char) not in supported for char in value):
            raise ValueError("Unsupported character in certificate text")
    temp = path.with_suffix("." + uuid.uuid4().hex + ".tmp")
    try:
        canvas = Canvas(str(temp), pagesize=landscape(A4))
        width, height = landscape(A4)
        canvas.setTitle("Certificate of achievement")

        # Outer hairline frame and an inner gold keyline for a formal border.
        canvas.setStrokeColorRGB(*INK_RGB)
        canvas.setLineWidth(1.2)
        canvas.rect(28, 28, width - 56, height - 56)
        canvas.setStrokeColorRGB(*GOLD_RGB)
        canvas.setLineWidth(2.4)
        canvas.rect(40, 40, width - 80, height - 80)
        canvas.setStrokeColorRGB(*GOLD_RGB)
        canvas.setLineWidth(0.6)
        canvas.rect(46, 46, width - 92, height - 92)

        # Short corner accents on the inner keyline.
        inset, reach = 46, 26
        canvas.setLineWidth(1.6)
        for x, dx in ((inset, 1), (width - inset, -1)):
            for y, dy in ((height - inset, -1), (inset, 1)):
                canvas.line(x, y, x + dx * reach, y)
                canvas.line(x, y, x, y + dy * reach)

        def text(value: str, top: float, size: int, slot: float, color: str, tracking: float = 0):
            for font_size in range(size, 5, -1):
                style = ParagraphStyle(
                    "center",
                    fontName="CertificateSans",
                    fontSize=font_size,
                    leading=font_size * 1.25,
                    alignment=TA_CENTER,
                    textColor=color,
                    splitLongWords=True,
                    charSpace=tracking,
                )
                paragraph = Paragraph(escape(value), style)
                _, used = paragraph.wrap(width - 150, slot)
                if used <= slot:
                    paragraph.drawOn(canvas, 75, top - used)
                    return
            raise ValueError("Text does not fit template")

        center = width / 2

        # Issuing organization as a tracked uppercase eyebrow.
        text(job.organization.upper(), 540, 15, 40, MUTED, 2.0)

        # Certificate title, the dominant element.
        text(job.title, 500, 34, 68, INK)

        # Gold divider beneath the title.
        canvas.setStrokeColorRGB(*GOLD_RGB)
        canvas.setLineWidth(1.4)
        canvas.line(center - 70, 432, center + 70, 432)

        text("THIS CERTIFICATE IS PROUDLY PRESENTED TO", 408, 12, 22, MUTED, 1.6)

        # Recipient name, elegant and prominent.
        text(name, 376, 34, 70, INK)

        # Thin rule under the recipient name.
        canvas.setStrokeColorRGB(*FAINT_RGB)
        canvas.setLineWidth(0.8)
        canvas.line(center - 185, 296, center + 185, 296)

        text(job.statement, 268, 16, 48, INK)
        text("in recognition of " + job.event, 206, 14, 42, MUTED)

        # Footer: issue date and signatory on signature lines.
        baseline = 118
        if job.signatory:
            left, right = center - 215, center + 215
            canvas.setStrokeColorRGB(*INK_RGB)
            canvas.setLineWidth(0.8)
            canvas.line(left - 95, baseline, left + 95, baseline)
            canvas.line(right - 95, baseline, right + 95, baseline)
            _footer_label(canvas, left, baseline, "DATE", job.issue_date)
            _footer_label(canvas, right, baseline, "AUTHORIZED SIGNATORY", job.signatory)
        else:
            text("Issued " + job.issue_date, baseline + 2, 13, 24, INK)

        # Certificate identifier for verification.
        text("Certificate ID: " + certificate_id, 62, 8, 14, MUTED, 0.5)

        canvas.showPage()
        canvas.save()
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _footer_label(canvas: Canvas, cx: float, line_y: float, label: str, value: str) -> None:
    # Value sits just above the signature line; a tracked label sits below it.
    canvas.setFont("CertificateSans", 12)
    canvas.setFillColorRGB(*INK_RGB)
    canvas.drawCentredString(cx, line_y + 6, _fit(canvas, value, 12, 180))
    canvas.setFont("CertificateSans", 8)
    canvas.setFillColorRGB(*GOLD_RGB)
    canvas.drawCentredString(cx, line_y - 14, label)


def _fit(canvas: Canvas, value: str, size: float, max_width: float) -> str:
    # Guard a single footer line from overflowing its signature rule.
    if canvas.stringWidth(value, "CertificateSans", size) <= max_width:
        return value
    ellipsis = "\u2026"
    trimmed = value
    while trimmed and canvas.stringWidth(trimmed + ellipsis, "CertificateSans", size) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + ellipsis) if trimmed else ellipsis
