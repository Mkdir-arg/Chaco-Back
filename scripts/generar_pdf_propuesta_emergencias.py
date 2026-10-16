"""Exporta la propuesta ejecutiva a dos páginas, con marca ICORE y sin fechas.

Dependencias de exportación: reportlab, pymupdf y resvg-py. No son dependencias
de la aplicación. Ejecutar con el venv del repositorio.
"""
from io import BytesIO
from pathlib import Path
import re

import pymupdf
import resvg_py
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs/client/propuestas"
ASSETS = DOCS / "assets"
SOURCE = DOCS / "propuesta-ejecutiva-emergencias.md"
OUTPUT = ASSETS / "propuesta-ejecutiva-icore-emergencias.pdf"
TEXT = SOURCE.read_text(encoding="utf-8")
WIDTH, HEIGHT = A4
MARGIN = 44
CONTENT = WIDTH - 2 * MARGIN
INK = colors.HexColor("#171A2C")
MUTED = colors.HexColor("#51566B")
PURPLE = colors.HexColor("#7042BC")
PALE = colors.HexColor("#F3EFFB")
LINE = colors.HexColor("#E2E4EC")

# La tipografía se incrusta en el PDF; no depende del equipo del lector.
font_root = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Proposal", str(font_root / "segoeui.ttf")))
pdfmetrics.registerFont(TTFont("ProposalBold", str(font_root / "segoeuib.ttf")))
pdfmetrics.registerFontFamily("Proposal", normal="Proposal", bold="ProposalBold")


def section(title):
    match = re.search(r"^#{2,3} " + re.escape(title) + r"\n(.*?)(?=^#{2,3} |\Z)", TEXT, re.M | re.S)
    assert match, title
    return match.group(1).strip()


def markup(text):
    return re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)


def paragraph(text, x, y, width=CONTENT, size=11, leading=16, color=INK, bold=False):
    style = ParagraphStyle("body", fontName="ProposalBold" if bold else "Proposal",
                           fontSize=size, leading=leading, textColor=color, alignment=TA_LEFT)
    p = Paragraph(markup(text), style)
    _, height = p.wrap(width, HEIGHT)
    assert y + height < HEIGHT - 45, f"Texto fuera de página ({y + height:.1f}): {text[:55]}"
    p.drawOn(c, x, HEIGHT - y - height)
    return y + height


def label(text, y):
    return paragraph(text, MARGIN, y, size=13.5, leading=18, bold=True) + 9


def header(page):
    c.drawImage(str(ASSETS / "icore/icore-logo.png"), MARGIN, HEIGHT - 72,
                width=126, height=26.88, mask="auto")
    c.setFillColor(MUTED)
    c.setFont("Proposal", 8)
    c.drawRightString(WIDTH - MARGIN, HEIGHT - 60, "PROPUESTA EJECUTIVA")
    c.setStrokeColor(LINE)
    c.line(MARGIN, 40, WIDTH - MARGIN, 40)
    c.setFont("Proposal", 8)
    c.drawString(MARGIN, 25, "ICORE  ·  Gestión social ante emergencias")
    c.drawRightString(WIDTH - MARGIN, 25, f"{page} / 2")


def body_section(title, y):
    y = label(title, y)
    for part in section(title).split("\n\n"):
        y = paragraph(part, MARGIN, y) + 8
    return y


def card(title, y, recommended=False):
    text, hours = section(title).split("\n\n")
    style = ParagraphStyle("measure", fontName="Proposal", fontSize=10.5, leading=14)
    p = Paragraph(text, style)
    _, ph = p.wrap(CONTENT - 32, HEIGHT)
    height = ph + 62
    c.setFillColor(PALE if recommended else colors.HexColor("#F7F8FB"))
    c.setStrokeColor(PURPLE if recommended else LINE)
    c.roundRect(MARGIN, HEIGHT - y - height, CONTENT, height, 9, fill=1, stroke=1)
    paragraph(title, MARGIN + 16, y + 12, CONTENT - 32, size=12, leading=16, bold=True,
              color=PURPLE if recommended else INK)
    paragraph(text, MARGIN + 16, y + 36, CONTENT - 32, size=10.5, leading=14)
    paragraph(hours, MARGIN + 16, y + 40 + ph, CONTENT - 32, size=9.5, leading=13, color=PURPLE)
    return y + height + 11


logo = ASSETS / "icore/icore-logo.svg"
logo.with_suffix(".png").write_bytes(resvg_py.svg_to_bytes(svg_path=str(logo), width=1125))
buffer = BytesIO()
c = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
c.setTitle("Plataforma Provincial de Gestión Social ante Emergencias | ICORE")
c.setAuthor("ICORE")
header(1)
y = paragraph("Plataforma Provincial<br/>de Gestión Social<br/>ante Emergencias", MARGIN, 98,
              size=29, leading=34, bold=True)
y = paragraph("Ministerio de Desarrollo Humano<br/>Provincia del Chaco", MARGIN, y + 15,
              size=11, leading=16, color=MUTED)
c.setStrokeColor(PURPLE)
c.setLineWidth(3)
c.line(MARGIN, HEIGHT - y - 17, MARGIN + 42, HEIGHT - y - 17)
y = body_section("Objetivo", y + 39)
y = label("Qué buscamos lograr", y + 12)
for item in section("Qué buscamos lograr").splitlines():
    c.setFillColor(PURPLE)
    c.circle(MARGIN + 3, HEIGHT - y - 8, 2.2, fill=1, stroke=0)
    y = paragraph(item.removeprefix("- "), MARGIN + 15, y, CONTENT - 15, size=10.5, leading=15) + 10
y = body_section("Una herramienta para la respuesta social", y + 8)
y = body_section("Cómo trabajaremos", y + 8)
c.showPage()

header(2)
y = paragraph("Tres alternativas.<br/>Un mismo objetivo.", MARGIN, 98, size=25, leading=30, bold=True)
y = paragraph(section("Tres alternativas para un mismo objetivo"), MARGIN, y + 11,
              size=10.5, leading=14, color=MUTED) + 17
for title in ("1. Esencial · Conocer y registrar", "2. Operativa · Organizar la atención",
              "3. Integral · Acompañar toda la respuesta"):
    y = card(title, y, recommended=title.startswith("3."))
y = paragraph("Nuestra recomendación: Integral", MARGIN, y + 2, size=12, leading=16, bold=True, color=PURPLE) + 6
y = paragraph(section("Nuestra recomendación"), MARGIN, y, size=10.5, leading=14) + 12
y = paragraph("<b>Acompañamiento opcional.</b> " + section("Acompañamiento opcional"), MARGIN, y,
              size=9.5, leading=13, color=MUTED) + 15
c.setStrokeColor(LINE)
c.setLineWidth(0.7)
c.line(MARGIN, HEIGHT - y, WIDTH - MARGIN, HEIGHT - y)
y = paragraph("Adaptación a las necesidades de la situación", MARGIN, y + 12,
              size=11.5, leading=15, bold=True) + 6
y = paragraph(section("Adaptación a las necesidades de la situación"), MARGIN, y, size=10, leading=14)
c.save()

pdf = pymupdf.open(stream=buffer.getvalue(), filetype="pdf")
pdf.set_metadata({"title": "Plataforma Provincial de Gestión Social ante Emergencias",
                  "author": "ICORE", "subject": "Propuesta ejecutiva", "creator": "ICORE",
                  "creationDate": "", "modDate": ""})
assert len(pdf) == 2
plain = " ".join("\n".join(page.get_text() for page in pdf).split())
assert "se ajustarán a las necesidades que demande la situación" in plain
assert not re.search(r"\b20\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b", plain)
assert all(word in plain for word in ("Esencial", "Operativa", "Integral", "6.500"))
pdf.save(OUTPUT, garbage=4, deflate=True)
print(f"PDF generado: {OUTPUT} | {len(pdf)} páginas | cierre en y={y:.1f}")
