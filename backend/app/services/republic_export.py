"""Respublika dinamikasi: Excel va PDF."""
import io
from datetime import date

import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import report_spec as S
from .reports import _fonts

REGION = "Qashqadaryo hududiy filiali"


def dmy(d) -> str:
    if not d:
        return ""
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return d.strftime("%d.%m.%Y")


def n(v) -> str:
    return "" if v is None else f"{v:,}".replace(",", " ")


def sgn(v) -> str:
    if v is None or v == 0:
        return ""
    return ("↑ " if v > 0 else "↓ ") + n(abs(v))


def rows_of(page: dict) -> list[tuple]:
    """(ko'rsatkich, oldingi, keyingi, farq, oy boshidan)"""
    out = []
    for c in page["cols"]:
        if c["bp"] is not None and c["b"] is None:
            out.append((c["label"] if c["label"] != "%" else "  %", c["ap"] or "", c["bp"], None, None, True))
        else:
            out.append((c["label"], n(c["a"]) if c["a"] is not None else "", n(c["b"]) if c["b"] is not None else "—",
                        c["diff"], c["d"], False))
    return out


def build_xlsx(pages: list[dict], a_date, b_date, month_start) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet("Respublika dinamikasi")
    ws.hide_gridlines(2)
    base = {"font_name": "Calibri", "font_size": 10, "valign": "vcenter"}
    f = lambda **k: wb.add_format({**base, **k})
    ws.set_column(0, 0, 52)
    ws.set_column(1, 4, 17)
    ws.merge_range(0, 0, 0, 4, f"{REGION} — respublika dinamikasi", f(bold=True, font_size=14, align="center"))
    ws.merge_range(1, 0, 1, 4, "D I N A M I K A", f(bold=True, font_size=12, align="center", font_color="#FF0000"))
    ws.merge_range(2, 0, 2, 4, f"Oy boshidan: {dmy(month_start)} – {dmy(b_date)}"
                   + (f"   |   Solishtirish: {dmy(a_date)} → {dmy(b_date)}" if a_date else ""),
                   f(bold=True, font_color="#0000FF", align="center"))
    r = 4
    head = f(bold=True, bg_color=S.HEAD_BG, border=1, align="center", text_wrap=True)
    cell = f(border=1)
    num = f(border=1, align="right", bold=True)
    for p in pages:
        ws.merge_range(r, 0, r, 4, p["title"], f(bold=True, font_size=11, bg_color=S.TOTAL_BG, border=1))
        r += 1
        for j, t in enumerate(["Ko'rsatkich", dmy(a_date) if a_date else "—", dmy(b_date), "Farq (kunma-kun)",
                               "Oy boshidan (PDF)"]):
            ws.write(r, j, t, head)
        r += 1
        for lab, a, b, diff, d, is_pct in rows_of(p):
            ws.write(r, 0, lab, cell)
            ws.write(r, 1, a, num)
            ws.write(r, 2, b, num)
            up = f(border=1, align="right", bold=True, font_color="#C00000" if (diff or 0) > 0 else "#0033CC")
            ws.write(r, 3, sgn(diff), up)
            ws.write(r, 4, sgn(d), f(border=1, align="right", font_color="#555555"))
            r += 1
        r += 1
    ws.freeze_panes(4, 0)
    wb.close()
    return buf.getvalue()


def build_pdf(pages: list[dict], a_date, b_date, month_start) -> bytes:
    _fonts()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=10 * mm,
                            bottomMargin=10 * mm, title="Respublika dinamikasi")
    ttl = ParagraphStyle("t", fontName="DV-B", fontSize=14, leading=18, alignment=1)
    sub = ParagraphStyle("s", fontName="DV-B", fontSize=11, leading=14, alignment=1, textColor=colors.HexColor("#FF0000"))
    per = ParagraphStyle("p", fontName="DV-B", fontSize=9, leading=12, alignment=1, textColor=colors.HexColor("#0000FF"))
    sec = ParagraphStyle("c", fontName="DV-B", fontSize=10, leading=13)
    story = [Paragraph(f"{REGION} — respublika dinamikasi", ttl), Spacer(1, 1.5 * mm), Paragraph("D I N A M I K A", sub),
             Spacer(1, 1.5 * mm),
             Paragraph(f"Oy boshidan: {dmy(month_start)} – {dmy(b_date)}"
                       + (f" &nbsp;|&nbsp; Solishtirish: {dmy(a_date)} → {dmy(b_date)}" if a_date else ""), per),
             Spacer(1, 4 * mm)]
    HB = colors.HexColor(S.HEAD_BG)
    for p in pages:
        data = [["Ko'rsatkich", dmy(a_date) if a_date else "—", dmy(b_date), "Farq", "Oy boshidan"]]
        st = [("FONTNAME", (0, 0), (-1, -1), "DV"), ("FONTSIZE", (0, 0), (-1, -1), 8),
              ("BACKGROUND", (0, 0), (-1, 0), HB), ("FONTNAME", (0, 0), (-1, 0), "DV-B"),
              ("GRID", (0, 0), (-1, -1), 0.4, colors.black), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.2),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)]
        for i, (lab, a, b, diff, d, is_pct) in enumerate(rows_of(p), start=1):
            data.append([lab, a, b, sgn(diff), sgn(d)])
            st.append(("FONTNAME", (1, i), (2, i), "DV-B"))
            if diff:
                st.append(("TEXTCOLOR", (3, i), (3, i), colors.HexColor("#C00000" if diff > 0 else "#0033CC")))
                st.append(("FONTNAME", (3, i), (3, i), "DV-B"))
            if d:
                st.append(("TEXTCOLOR", (4, i), (4, i), colors.HexColor("#555555")))
        t = Table(data, colWidths=[78 * mm, 27 * mm, 27 * mm, 27 * mm, 27 * mm], style=TableStyle(st), repeatRows=1)
        story.append(KeepTogether([Paragraph(p["title"], sec), Spacer(1, 1 * mm), t, Spacer(1, 4 * mm)]))
    doc.build(story)
    return buf.getvalue()
