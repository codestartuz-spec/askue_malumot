"""Dinamika hisobotlari: Excel va PDF."""
import html
import io
from datetime import date

import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..config import BASE
from . import report_spec as S

_FONTS = BASE / "assets" / "fonts"
_registered = False


def _fonts() -> None:
    global _registered
    if not _registered:
        pdfmetrics.registerFont(TTFont("DV", str(_FONTS / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DV-B", str(_FONTS / "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B")
        _registered = True


def dmy(iso: str | None) -> str:
    return ".".join(reversed(iso.split("-"))) if iso else ""


def period(data: dict) -> str:
    if data.get("base"):
        return f"{dmy(data['base'])} – {dmy(data['to'])}"
    return dmy(data.get("to"))


REGION_NAME = "Qashqadaryo hududiy filiali"


def title_of(table: str, scope: str) -> str:
    return f"{scope} {S.TABLES[table]['title']}"


def _body_rows(data: dict):
    """[(nom, cur, base, is_total)] — birinchi qator 'Jami'."""
    tot = data["total"]
    rows = [("Jami", tot["cur"], tot["base"], True)]
    rows += [(r["name"] + ("\n" + ", ".join(r["members"]) if r.get("members") else ""), r["cur"], r["base"], False)
             for r in data["rows"]]
    return rows


# --------------------------------------------------------------------- Excel
def build_xlsx(items: list[tuple[str, dict]], scope: str, first_col: str) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    fcache: dict = {}

    def fmt(**kw):
        key = tuple(sorted(kw.items()))
        if key not in fcache:
            fcache[key] = wb.add_format({"font_name": "Calibri", "font_size": 10, "valign": "vcenter", **kw})
        return fcache[key]

    for table, data in items:
        cfg = S.TABLES[table]
        ws = wb.add_worksheet(cfg["short"][:30])
        ws.hide_gridlines(2)
        ncols = 1 + len(cfg["cols"])
        ws.merge_range(0, 0, 0, ncols - 1, title_of(table, scope), fmt(bold=True, font_size=14, align="center"))
        ws.merge_range(1, 0, 1, ncols - 1, "D I N A M I K A", fmt(bold=True, font_size=12, align="center",
                                                                 font_color="#FF0000"))
        ws.write(2, 0, "Hudud nomi:", fmt(align="right"))
        ws.merge_range(2, 1, 2, 4, scope, fmt(bold=True, font_color="#0070C0", border=1, border_color="#00B0F0",
                                              align="left"))
        ws.merge_range(2, max(ncols - 7, 6), 2, ncols - 1, f"Dinamika: {period(data)}",
                       fmt(bold=True, font_color="#0000FF", align="right"))
        top = 4
        heads = [[(l if l != "Hudud nomi" else first_col, rs, cs, c) for (l, rs, cs, c) in row]
                 for row in cfg["head"]]
        for r, c, rs, cs, label, cls in S.place_header(heads, ncols):
            st = S.head_style(cls)
            kw = dict(bold=True, font_color=st["color"], bg_color=S.HEAD_BG, align="center", text_wrap=True,
                      border=1, italic=st["it"], font_size=8 if st["small"] else 10)
            if st["vert"]:
                kw.update(rotation=90, font_size=9)
            if label == first_col:
                kw["font_size"] = 12
            f = fmt(**kw)
            rich = st["arr"]
            if rs == 1 and cs == 1:
                if rich:
                    ws.write_rich_string(top + r, c, fmt(font_color="#FF0000", bold=True), "↑", fmt(font_color="#0033CC", bold=True), "↓", fmt(**kw))
                else:
                    ws.write(top + r, c, label, f)
            else:
                ws.merge_range(top + r, c, top + r + rs - 1, c + cs - 1, "" if rich else label, f)
                if rich:
                    ws.write_rich_string(top + r, c, fmt(font_color="#FF0000", bold=True), "↑", fmt(font_color="#0033CC", bold=True), "↓", f)
        start = top + len(cfg["head"])
        for i, (name, cur, base, total) in enumerate(_body_rows(data)):
            bg = S.TOTAL_BG if total else "#FFFFFF"
            ws.write(start + i, 0, name, fmt(bold=total, bg_color=bg, border=1, align="center" if total else "left",
                                             font_size=11 if total else 10, text_wrap=True))
            if "\n" in name:
                ws.set_row(start + i, 13 * (1 + -(-len(name.split(chr(10))[1]) // 38)) + 2)
            for j, col in enumerate(cfg["cols"], start=1):
                txt, color, bold = S.cell_values(col, cur, base)
                kw = dict(bg_color=bg, border=1, align="center", bold=bold or total)
                if color:
                    kw["font_color"] = S.COLORS.get(color, "#000000")
                if col[0] == "n" and txt:
                    ws.write_number(start + i, j, int(cur.get(col[1], 0)), fmt(**kw, num_format="#,##0"))
                else:
                    ws.write(start + i, j, txt, fmt(**kw))
        ws.set_column(0, 0, 40 if any("\n" in b[0] for b in _body_rows(data)) else 24)
        ws.set_column(1, ncols - 1, 11)
        for r in range(len(cfg["head"])):
            ws.set_row(top + r, 36 if r < 3 else 22)
        ws.freeze_panes(start, 1)
        ws.set_landscape()
        ws.fit_to_pages(1, 0)
        ws.set_paper(8)
    wb.close()
    return buf.getvalue()


# ----------------------------------------------------------------------- PDF
class Rot(Flowable):
    """90° burilgan (pastdan yuqoriga) matn — tor ustun sarlavhalari uchun."""

    def __init__(self, text, w, h, size, color, bold=True):
        super().__init__()
        self.w, self.h, self.size, self.color = w, h, size, color
        self.font = "DV-B" if bold else "DV"
        lim = h - 3 * mm
        lines, cur = [], ""
        for word in text.split():
            t = (cur + " " + word).strip()
            if stringWidth(t, self.font, size) <= lim or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
        self.lines = lines

    def wrap(self, aw, ah):
        return self.w, self.h

    def draw(self):
        c = self.canv
        c.saveState()
        c.translate(self.w / 2, self.h / 2)
        c.rotate(90)
        c.setFillColor(colors.HexColor(self.color))
        c.setFont(self.font, self.size)
        lead = self.size * 1.25
        n = len(self.lines)
        for i, ln in enumerate(self.lines):
            c.drawCentredString(0, ((n - 1) / 2 - i) * lead - self.size * 0.33, ln)
        c.restoreState()


def build_pdf(items: list[tuple[str, dict]], scope: str, first_col: str) -> bytes:
    _fonts()
    buf = io.BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=8 * mm, rightMargin=8 * mm, topMargin=8 * mm,
                            bottomMargin=8 * mm, title="ASKUE ma'lumot — dinamika", author="ASKUE ma'lumot")
    black = colors.black
    ttl = ParagraphStyle("t", fontName="DV-B", fontSize=13, leading=16, alignment=1, textColor=black)
    sub = ParagraphStyle("s", fontName="DV-B", fontSize=11, leading=14, alignment=1, textColor=colors.HexColor("#FF0000"))
    note = ParagraphStyle("n", fontName="DV", fontSize=7, leading=9, textColor=colors.HexColor("#64748B"))
    lab = ParagraphStyle("l", fontName="DV", fontSize=9, leading=12, alignment=2)
    box = ParagraphStyle("b", fontName="DV-B", fontSize=9, leading=12, textColor=colors.HexColor("#0070C0"))
    per = ParagraphStyle("p", fontName="DV-B", fontSize=9, leading=12, alignment=2, textColor=colors.HexColor("#0000FF"))
    story = []
    avail = page[0] - 16 * mm
    avail_h = page[1] - 16 * mm
    for k, (table, data) in enumerate(items):
        if k:
            story.append(PageBreak())
        cfg = S.TABLES[table]
        ncols = 1 + len(cfg["cols"])
        story += [Paragraph(title_of(table, scope), ttl), Spacer(1, 1.5 * mm),
                  Paragraph("D I N A M I K A", sub), Spacer(1, 2 * mm)]
        info = Table([[Paragraph("Hudud nomi:", lab), Paragraph(scope, box), "", Paragraph(f"Dinamika: {period(data)}", per)]],
                     colWidths=[26 * mm, 60 * mm, avail - 86 * mm - 80 * mm, 80 * mm])
        info.setStyle(TableStyle([("BOX", (1, 0), (1, 0), 0.8, colors.HexColor("#00B0F0")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                  ("LEFTPADDING", (1, 0), (1, 0), 4)]))
        story += [info, Spacer(1, 2 * mm)]
        heads = [[(l if l != "Hudud nomi" else first_col, rs, cs, c) for (l, rs, cs, c) in row] for row in cfg["head"]]
        nh = len(heads)
        name_w = 46 * mm if any('\n' in b[0] for b in _body_rows(data)) else 30 * mm
        w = (avail - name_w) / (ncols - 1)
        hh = 9 * mm if len(cfg['head']) >= 4 else 10.5 * mm
        grid = [[""] * ncols for _ in range(nh)]
        gl = colors.black
        style = [("FONTNAME", (0, 0), (-1, -1), "DV"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                 ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("GRID", (0, 0), (-1, -1), 0.5, gl),
                 ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                 ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                 ("BACKGROUND", (0, 0), (-1, nh - 1), colors.HexColor(S.HEAD_BG))]
        for r, c, rs, cs, label, cls in S.place_header(heads, ncols):
            st = S.head_style(cls)
            size = 6 if st["small"] else 7.5
            if label == first_col:
                size = 10
            if st["arr"]:
                cell = Paragraph('<font color="#FF0000">↑</font><font color="#0033CC">↓</font>',
                                 ParagraphStyle("a", fontName="DV-B", fontSize=8, leading=10, alignment=1))
            elif st["vert"]:
                cw = name_w if c == 0 else w * cs
                cell = Rot(label, cw, hh * rs, 6.5, st["color"])
            else:
                fn = "DV-B"
                cell = Paragraph(f'<i>{label}</i>' if st["it"] else label,
                                 ParagraphStyle("h", fontName=fn, fontSize=size, leading=size + 2, alignment=1,
                                                textColor=colors.HexColor(st["color"])))
            grid[r][c] = cell
            if rs > 1 or cs > 1:
                style.append(("SPAN", (c, r), (c + cs - 1, r + rs - 1)))
        tall: dict[int, float] = {}
        for i, (name, cur, base, total) in enumerate(_body_rows(data)):
            r = nh + i
            if "\n" in name:
                nm, mem = name.split("\n", 1)
                row = [[Paragraph(f"<b>{nm}</b>", ParagraphStyle("nm", fontName="DV", fontSize=8.5, leading=10)),
                        Paragraph(html.escape(mem), ParagraphStyle("mm", fontName="DV", fontSize=6.5, leading=7.6,
                                                                   textColor=colors.HexColor("#475569")))]]
                tall[r] = (6.6 + 2.75 * (-(-len(mem) // 29))) * mm
            else:
                row = [name]
            for j, col in enumerate(cfg["cols"], start=1):
                txt, color, bold = S.cell_values(col, cur, base)
                row.append(txt)
                if color:
                    style.append(("TEXTCOLOR", (j, r), (j, r), colors.HexColor(S.COLORS.get(color, "#000000"))))
                if bold or total:
                    style.append(("FONTNAME", (j, r), (j, r), "DV-B"))
            grid.append(row)
            if total:
                style.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor(S.TOTAL_BG)))
                style.append(("FONTNAME", (0, r), (0, r), "DV-B"))
            else:
                style.append(("ALIGN", (0, r), (0, r), "LEFT"))
        nbody = len(grid) - nh
        n_norm = max(nbody - len(tall), 1)
        used = 33 * mm + hh * nh + sum(tall.values()) + 7 * mm      # sarlavha bloki + jadval sarlavhasi + izoh
        rh = max(5.6 * mm, min((avail_h - used) / n_norm, 15 * mm))
        fs = max(6.6, min(rh / mm * 1.18, 9.5 if nbody <= 2 else 10.5))
        style.append(("FONTSIZE", (0, nh), (-1, -1), fs))
        t = Table(grid, colWidths=[name_w] + [w] * (ncols - 1), rowHeights=[hh] * nh + [tall.get(nh + k, rh) for k in range(nbody)],
                  repeatRows=nh)
        t.setStyle(TableStyle(style))
        story += [t, Spacer(1, 4 * mm), Paragraph(f"Hisobot sanasi: {date.today():%d.%m.%Y} • ASKUE ma'lumot", note)]
    doc.build(story)
    return buf.getvalue()
