"""Renderers: Markdown (canonical) -> Markdown | DOCX | PDF. A registry keyed by format (strategy pattern)."""
from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from archtwin.exports.blocks import MERMAID_CAPTION, parse, plain, runs


@dataclass(frozen=True)
class Format:
    key: str
    ext: str
    media_type: str
    render: Callable[[str, str], bytes]          # (title, markdown) -> bytes


def render_md(title: str, md: str) -> bytes:
    return md.encode("utf-8")


# ------------------------------------------------------------------ DOCX
def render_docx(title: str, md: str) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    doc = Document()
    doc.core_properties.title = title[:200]
    doc.core_properties.author = "ArchTwin"
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(10.5)

    def add_runs(p, text: str) -> None:
        for t, style in runs(text):
            r = p.add_run(t)
            r.bold = style == "bold"
            r.italic = style == "italic"
            if style == "code":
                r.font.name, r.font.size = "Consolas", Pt(9.5)

    for b in parse(md):
        if b.kind == "heading":
            first = not doc.paragraphs
            doc.add_heading(plain(b.text), level=0 if b.level == 1 and first else min(max(b.level - 1, 1), 4))
        elif b.kind == "para":
            add_runs(doc.add_paragraph(), b.text)
        elif b.kind in ("bullets", "numbers"):
            for it in b.items:
                add_runs(doc.add_paragraph(style="List Bullet" if b.kind == "bullets" else "List Number"), it)
        elif b.kind == "quote":
            p = doc.add_paragraph(style="Intense Quote")
            add_runs(p, b.text)
        elif b.kind == "rule":
            doc.add_paragraph("―" * 30).alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif b.kind == "table" and b.rows:
            t = doc.add_table(rows=len(b.rows), cols=len(b.rows[0]))
            t.style = "Light Grid Accent 1"
            for ri, row in enumerate(b.rows):
                for ci, cell in enumerate(row):
                    c = t.cell(ri, ci)
                    c.text = ""
                    add_runs(c.paragraphs[0], cell)
                    if ri == 0:
                        for r in c.paragraphs[0].runs:
                            r.bold = True
            doc.add_paragraph()
        elif b.kind == "code":
            if b.lang == "mermaid":
                cap = doc.add_paragraph()
                cr = cap.add_run(MERMAID_CAPTION)
                cr.italic, cr.font.size = True, Pt(9)
                cr.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
            p = doc.add_paragraph()
            r = p.add_run(b.text)
            r.font.name, r.font.size = "Consolas", Pt(8.5)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ PDF
FONT_DIRS = ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/usr/local/share/fonts")


def _font_files() -> dict[str, str] | None:
    for d in FONT_DIRS:
        p = Path(d)
        regular, mono = p / "DejaVuSans.ttf", p / "DejaVuSansMono.ttf"
        if regular.exists() and mono.exists():            # bold/oblique are optional (fonts-dejavu-core has no oblique)
            bold, italic = p / "DejaVuSans-Bold.ttf", p / "DejaVuSans-Oblique.ttf"
            return {"": str(regular), "B": str(bold if bold.exists() else regular), "I": str(italic if italic.exists() else regular),
                    "mono": str(mono)}
    return None


def render_pdf(title: str, md: str) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_title(title[:200])
    pdf.set_author("ArchTwin")
    fonts = _font_files()
    if fonts:
        pdf.add_font("body", "", fonts[""])
        pdf.add_font("body", "B", fonts["B"])
        pdf.add_font("body", "I", fonts["I"])
        pdf.add_font("mono", "", fonts["mono"])
        body, mono = "body", "mono"

        def clean(s: str) -> str:
            return s
    else:                                         # core fonts are Latin-1 only: degrade gracefully
        body, mono = "helvetica", "courier"

        def clean(s: str) -> str:
            return s.replace("→", "->").replace("←", "<-").replace("—", "-").replace("–", "-").replace("…", "...") \
                .replace("“", '"').replace("”", '"').replace("’", "'").replace("•", "*").encode("latin-1", "replace").decode("latin-1")
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    def para(text: str, size: float = 10, style: str = "", indent: float = 0, h: float = 5.2) -> None:
        pdf.set_x(pdf.l_margin + indent)
        pdf.set_font(body, style, size)
        md_text = "".join(f"**{t}**" if s == "bold" else f"__{t}__" if s == "italic" else t for t, s in runs(text)) if style == "" else plain(text)
        pdf.multi_cell(width - indent, h, clean(md_text), markdown=style == "", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    sizes = {1: 18, 2: 14, 3: 12, 4: 11, 5: 10.5, 6: 10}
    for b in parse(md):
        if b.kind == "heading":
            pdf.ln(2 if b.level > 2 else 4)
            para(b.text, sizes.get(b.level, 10), "B", h=sizes.get(b.level, 10) * 0.5)
            pdf.ln(1)
        elif b.kind == "para":
            para(b.text)
            pdf.ln(1.5)
        elif b.kind in ("bullets", "numbers"):
            for n, it in enumerate(b.items, 1):
                para(f"{'•' if b.kind == 'bullets' else f'{n}.'} {it}", indent=4)
            pdf.ln(1.5)
        elif b.kind == "quote":
            pdf.set_text_color(90, 90, 90)
            para(b.text, indent=6)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1.5)
        elif b.kind == "rule":
            pdf.line(pdf.l_margin, pdf.get_y() + 2, pdf.w - pdf.r_margin, pdf.get_y() + 2)
            pdf.ln(5)
        elif b.kind == "table" and b.rows:
            pdf.set_font(body, "", 8)
            with pdf.table(width=width, text_align="LEFT", line_height=4.2, first_row_as_headings=True) as t:
                for row in b.rows:
                    r = t.row()
                    for cell in row:
                        r.cell(clean(plain(cell))[:600])
            pdf.ln(2)
        elif b.kind == "code":
            if b.lang == "mermaid":
                pdf.set_font(body, "I", 8)
                pdf.set_text_color(100, 100, 100)
                pdf.multi_cell(width, 4, MERMAID_CAPTION, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(0, 0, 0)
            pdf.set_font(mono, "", 7.5)
            pdf.set_fill_color(245, 245, 245)
            pdf.multi_cell(width, 3.6, clean(b.text[:20000]), fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
    return bytes(pdf.output())


FORMATS: dict[str, Format] = {
    "md": Format("md", "md", "text/markdown; charset=utf-8", render_md),
    "docx": Format("docx", "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", render_docx),
    "pdf": Format("pdf", "pdf", "application/pdf", render_pdf),
}

