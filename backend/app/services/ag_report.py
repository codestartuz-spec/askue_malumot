"""AG dinamikasi hisobotlari (PDF va Excel) — asl «AG» PDF dizaynida: A4 albom, och ko'k sarlavha,
sariq «Jami» qatori, ↑↓ o'zgarishlar va uch ustunda foizli chiziqchalar (data bar)."""
import io

import xlsxwriter
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas

from . import reports as RP
from .ag import DEFAULT_REGION, DEFAULT_TITLE, NG

PW, PH = 841.68, 595.2
XS = [15.9, 150.6, 190.4, 232.6, 262.2, 294.1, 329.5, 378.6, 411.6, 450.4, 491.2, 522.1, 562.5, 592.0, 634.2,
      663.8, 706.5, 740.9, 785.1, 822.4]
Y0, YB, YC, YJ = 89.7, 107.0, 118.0, 151.2          # sarlavha qatorlari chegaralari
Y1 = 170.2                                           # «Jami» qatori tagi
ROW_H, TOT_H = 17.3, 19.0

HB = "#D9E1F2"          # sarlavha
PINK = "#FFE6E6"        # «shundan» sarlavhasi
TOTAL_BG = "#FFE699"
RED = "#C00000"
DKRED = "#860404"
GREEN = "#00B050"
SKY = "#00B0F0"
UP, DOWN = "#FF0000", "#0000FF"
BAR = {4: "#F8CBAD", 7: "#FFD966", 8: "#FFD966"}     # foizli chiziqcha: guruh → rang

VAL_T = [GREEN, GREEN, GREEN, GREEN, RED, DKRED, DKRED, RED, RED]       # «Jami» qatori qiymat rangi
VAL_D = ["#000000"] * 4 + [RED, "#000000", "#000000", RED, RED]         # hudud qatori qiymat rangi
VAL_SZ_D = [7.9, 7.9, 7.9, 7.9, 7.9, 9.7, 9.7, 7.9, 7.9]                # hudud qatori qiymat o'lchami
DLT_SZ_D = [6.7] * 7 + [7.3, 7.3]                                       # hudud qatori ↑↓ o'lchami
DLT_SZ_T = [7.3] * 4 + [5.5] * 3 + [7.3] * 2                              # «Jami» qatori ↑↓ o'lchami

# Sarlavha katagi: (x0 ind, x1 ind, y0, y1, fill, [qatorlar [(matn, rang)]], o'lcham, shrift)
BK = "#000000"
HEAD = [
    (0, 1, Y0, YJ, HB, [[("Hudud", BK)]], 11.0, "CA-B"),
    (1, 9, Y0, YC, HB, [[("CAS dasturidagi hodisalar", BK)]], 11.0, "CA-B"),
    (1, 3, YC, YJ, HB, [[("Kirish va chiqish ", BK), ("quvvati", UP)], [("orasidagi", BK)], [("nomutanosiblik", BK)]], 7.9, "CA-B"),
    (3, 5, YC, YJ, HB, [[("Hisoblagich", BK)], [("qutisi ochilgan", BK)]], 8.5, "CA-B"),
    (5, 7, YC, YJ, HB, [[("Klemmasi ochilgan", BK)]], 8.5, "CA-B"),
    (7, 9, YC, YJ, HB, [[("Kuchlanishsiz tok", BK)], [("oqib o'tayotgan", BK)]], 8.5, "CA-B"),
    (9, 15, Y0, YB, HB, [[("Aloqadan chiqib ketgan hisoblagichlar", RED)]], 8.5, "CA-B"),
    (9, 11, YB, YJ, HB, [[("Jami Soni", BK)]], 8.5, "CA-B"),
    (11, 15, YB, YC, PINK, [[("shundan", BK)]], 8.5, "CA-BI"),
    (11, 13, YC, YJ, PINK, [[("1-3 oy", BK)]], 8.5, "CA-BI"),
    (13, 15, YC, YJ, PINK, [[("3 oydan ortiq", BK)]], 8.5, "CA-BI"),
    (15, 17, Y0, YJ, HB, [[("Kirish va chiqish", RED)], [("simlari", RED)], [("tutashtirilgan", RED)],
                          [("(перемичка)", SKY)]], 9.1, "CA-B"),
    (17, 19, Y0, YJ, HB, [[("Aloqaga chiqmagan", RED)], [("hisoblagichlar", RED)]], 9.1, "CA-B"),
]


def _n(v) -> str:
    return f"{int(round(v)):,}".replace(",", " ")


def _hex(c):
    return colors.HexColor(c)


def _delta_txt(cur: dict, base: dict, g: int) -> tuple[str, str] | None:
    dv = cur.get(f"c{g}", 0) - base.get(f"c{g}", 0)
    if dv == 0:
        return None
    return (("↑ " + _n(dv)), UP) if dv > 0 else (("↓ -" + _n(abs(dv))), DOWN)


def _period(res: dict) -> str:
    f, t = res["from"], res["to"]
    return f"{RP.dmy(f)} - {RP.dmy(t)}"


def _fit(text: str, font: str, size: float, width: float, floor: float = 4.5) -> float:
    while size > floor and stringWidth(text, font, size) > width:
        size -= 0.2
    return size


def _lines(c, xa, xb, ya, yb, lines, size, font):
    """Katak ichida qatorlarni markazlab chizadi (y — yuqoridan o'lchangan)."""
    w = xb - xa
    while True:
        wd = [sum(stringWidth(t, font, size) for t, _ in ln) for ln in lines]
        if max(wd) <= w - 3 or size <= 5:
            break
        size -= 0.2
    lead = size * 1.3
    n = len(lines)
    cy = (ya + yb) / 2
    for i, ln in enumerate(lines):
        yc = cy + (i - (n - 1) / 2) * lead
        x = (xa + xb) / 2 - wd[i] / 2
        for t, col in ln:
            c.setFillColor(_hex(col))
            c.setFont(font, size)
            c.drawString(x, PH - (yc + size * 0.32), t)
            x += stringWidth(t, font, size)


def build_pdf(res: dict) -> bytes:
    RP._fonts()
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PW, PH), pageCompression=1)
    c.setTitle("AG dinamikasi")
    c.setAuthor("ASKUE ma'lumot")
    rows = res["rows"]
    n = len(rows)
    row_h = min(ROW_H, (PH - 26 - Y1) / max(n, 1))
    f = row_h / ROW_H
    ybot = Y1 + n * row_h
    cx = (XS[0] + XS[-1]) / 2
    y = lambda t: PH - t   # noqa: E731

    # sarlavha bloki
    c.setFillColor(colors.black)
    c.setFont("CA-B", 12.2)
    c.drawCentredString(cx, y(42.5), res.get("title") or DEFAULT_TITLE)
    c.setFillColor(_hex("#FF0000"))
    c.setFont("CA-B", 15.8)
    c.drawCentredString(cx, y(62.2), "Ma'lumot")
    c.setFillColor(colors.black)
    c.setFont("CA-B", 9.7)
    c.drawString(76.4, y(76.0), "Hudud Nomi:")
    c.setStrokeColor(_hex(SKY))
    c.setLineWidth(0.6)
    c.rect(190.7, y(79.8), 139.1, 14.3)
    c.setFillColor(_hex(SKY))
    c.setFont("CA-B", 11.0)
    c.drawString(199.8, y(76.4), res.get("region") or DEFAULT_REGION)
    c.setFillColor(_hex("#0000FF"))
    c.setFont("CA-B", 9.1)
    c.drawRightString(799.7, y(75.6), f"Farq: {_period(res)}")

    # sarlavha kataklari
    for xa, xb, ya, yb, fill, lines, size, font in HEAD:
        c.setFillColor(_hex(fill))
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.5)
        c.rect(XS[xa], y(yb), XS[xb] - XS[xa], yb - ya, fill=1, stroke=1)
    for xa, xb, ya, yb, fill, lines, size, font in HEAD:
        _lines(c, XS[xa], XS[xb], ya, yb, lines, size, font)

    # «Jami» qatori
    cur, base = res["cur"], res["base"]
    c.setFillColor(_hex(TOTAL_BG))
    c.setStrokeColor(colors.black)
    c.rect(XS[0], y(Y1), XS[0 + 1] - XS[0], Y1 - YJ, fill=1, stroke=1)
    c.setFillColor(colors.black)
    c.setFont("CA-B", 11.0)
    c.drawCentredString((XS[0] + XS[1]) / 2, y((YJ + Y1) / 2 + 3.5), "Jami")
    mid = (YJ + Y1) / 2
    for g in range(NG):
        xv0, xv1, xd1 = XS[1 + 2 * g], XS[2 + 2 * g], XS[3 + 2 * g]
        for xa, xb in ((xv0, xv1), (xv1, xd1)):
            c.setFillColor(_hex(TOTAL_BG))
            c.rect(xa, y(Y1), xb - xa, Y1 - YJ, fill=1, stroke=1)
        v = cur.get(f"c{g}", 0)
        txt = _n(v) if v else "-"
        c.setFillColor(_hex(VAL_T[g]))
        c.setFont("CA-B", 9.7)
        c.drawRightString(xv1 - 1.6, y(mid + 3.1), txt)
        dt = _delta_txt(cur, base, g)
        if dt:
            sz = _fit(dt[0], "CA-B", DLT_SZ_T[g], xd1 - xv1 - 2.6)
            c.setFillColor(_hex(dt[1]))
            c.setFont("CA-B", sz)
            c.drawRightString(xd1 - 1.3, y(mid + sz * 0.32), dt[0])

    # hudud qatorlari
    mx = {g: max((r["cur"].get(f"c{g}", 0) for r in rows), default=0) for g in BAR}
    for i, r in enumerate(rows):
        yt = Y1 + i * row_h
        yb_ = yt + row_h
        mid = yt + row_h / 2
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.5)
        c.rect(XS[0], y(yb_), XS[1] - XS[0], row_h, fill=1, stroke=1)
        c.setFillColor(colors.black)
        c.setFont("CA", 8.5 * f)
        c.drawString(XS[0] + 8.8, y(mid + 8.5 * f * 0.32), r["name"])
        for g in range(NG):
            xv0, xv1, xd1 = XS[1 + 2 * g], XS[2 + 2 * g], XS[3 + 2 * g]
            c.setFillColor(colors.white)
            c.rect(xv0, y(yb_), xv1 - xv0, row_h, fill=1, stroke=1)
            c.rect(xv1, y(yb_), xd1 - xv1, row_h, fill=1, stroke=1)
            v = r["cur"].get(f"c{g}", 0)
            if g in BAR and mx[g] > 0 and v > 0:
                bw = max((xv1 - xv0 - 2.9) * v / mx[g], 0.2)
                c.setFillColor(_hex(BAR[g]))
                c.rect(xv0 + 1.4, y(yb_ - 1.95 * f), bw, row_h - 3.9 * f, fill=1, stroke=0)
            if v:
                sz = _fit(_n(v), "CA-B", VAL_SZ_D[g] * f, xv1 - xv0 - 2.6)
                c.setFillColor(_hex(VAL_D[g]))
                c.setFont("CA-B", sz)
                c.drawRightString(xv1 - 1.6, y(mid + sz * 0.32), _n(v))
            dt = _delta_txt(r["cur"], r["base"], g)
            if dt:
                sz = _fit(dt[0], "CA-B", DLT_SZ_D[g] * f, xd1 - xv1 - 2.6)
                c.setFillColor(_hex(dt[1]))
                c.setFont("CA-B", sz)
                c.drawRightString(xd1 - 1.3, y(mid + sz * 0.32), dt[0])
    # tashqi ramka
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.rect(XS[0], y(ybot), XS[-1] - XS[0], ybot - Y0, fill=0, stroke=1)
    c.showPage()
    c.save()
    return buf.getvalue()


# --------------------------------------------------------------------- Excel
K = 1.45


def _cw(pt: float) -> float:
    """PDF kengligi (pt) → Excel ustun kengligi (belgi)."""
    return max((pt * K / 0.75 - 5) / 7, 2)


def build_xlsx(res: dict) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet("AG dinamikasi")
    ws.hide_gridlines(2)
    cache: dict = {}

    def fmt(**kw):
        key = tuple(sorted(kw.items()))
        if key not in cache:
            cache[key] = wb.add_format({"font_name": "Calibri", "font_size": 11, "valign": "vcenter", **kw})
        return cache[key]

    sz = lambda v: round(v * K * 2) / 2   # noqa: E731
    ncols = 19
    ws.set_column(0, 0, _cw(XS[1] - XS[0]))
    for j in range(1, ncols):
        ws.set_column(j, j, _cw(XS[j + 1] - XS[j]))
    cur, base, rows = res["cur"], res["base"], res["rows"]

    ws.merge_range(0, 0, 0, ncols - 1, res.get("title") or DEFAULT_TITLE, fmt(bold=True, font_size=sz(12.2), align="center"))
    ws.merge_range(1, 0, 1, ncols - 1, "Ma'lumot", fmt(bold=True, font_size=sz(15.8), align="center", font_color="#FF0000"))
    ws.write(2, 0, "Hudud Nomi:", fmt(bold=True, font_size=sz(9.7), align="right"))
    ws.merge_range(2, 1, 2, 4, res.get("region") or DEFAULT_REGION,
                   fmt(bold=True, font_size=sz(11), font_color=SKY, border=1, border_color=SKY, align="left"))
    ws.merge_range(2, 12, 2, ncols - 1, f"Farq: {_period(res)}", fmt(bold=True, font_size=sz(9.1), font_color="#0000FF", align="right"))
    ws.set_row(0, 22 * 1.2)
    ws.set_row(1, 26)
    ws.set_row(2, 22)
    top = 4                                          # sarlavha birinchi qatori (0-asosli)
    hrows = [top, top + 1, top + 2]
    for r, h in zip(hrows, (YB - Y0, YC - YB, YJ - YC)):
        ws.set_row(r, h * K)
    rmap = {Y0: top, YB: top + 1, YC: top + 2, YJ: top + 3}
    # sarlavha: Excel'da sakkiz ustunli guruhlar uchun (x indekslari XS → ustun: i-ustun = XS[i]..XS[i+1])
    for xa, xb, ya, yb, fill, lines, size, font in HEAD:
        r0, r1 = rmap[ya], rmap[yb] - 1
        c0, c1 = xa, xb - 1
        text_parts = []
        for k, ln in enumerate(lines):
            if k:
                text_parts.append(("\n", None))
            text_parts += [(t, col) for t, col in ln]
        base_fmt = dict(bold=True, font_size=sz(size), bg_color=fill, align="center", text_wrap=True, border=1,
                        italic=font == "CA-BI")
        if len({col for _, col in text_parts if col}) > 1:
            rich = []
            for t, col in text_parts:
                rich.append(fmt(bold=True, font_size=sz(size), font_color=col or "#000000"))
                rich.append(t)
            if (r0, c0) == (r1, c1):
                ws.write_rich_string(r0, c0, *rich, fmt(**base_fmt))
            else:
                ws.merge_range(r0, c0, r1, c1, "", fmt(**base_fmt))
                ws.write_rich_string(r0, c0, *rich, fmt(**base_fmt))
        else:
            col = next((cc for _, cc in text_parts if cc), "#000000")
            txt = "".join(t for t, _ in text_parts)
            f_ = fmt(**base_fmt, font_color=col)
            if (r0, c0) == (r1, c1):
                ws.write(r0, c0, txt, f_)
            else:
                ws.merge_range(r0, c0, r1, c1, txt, f_)
    # «Jami» qatori
    rj = top + 3
    ws.set_row(rj, TOT_H * K)
    ws.write(rj, 0, "Jami", fmt(bold=True, font_size=sz(11), bg_color=TOTAL_BG, align="center", border=1))
    for g in range(NG):
        v = cur.get(f"c{g}", 0)
        vf = fmt(bold=True, font_size=sz(9.7), font_color=VAL_T[g], bg_color=TOTAL_BG, align="right", border=1, num_format="#,##0")
        if v:
            ws.write_number(rj, 1 + 2 * g, v, vf)
        else:
            ws.write_string(rj, 1 + 2 * g, "-", vf)
        dt = _delta_txt(cur, base, g)
        ws.write_string(rj, 2 + 2 * g, dt[0] if dt else "",
                        fmt(bold=True, font_size=sz(DLT_SZ_T[g]), font_color=dt[1] if dt else "#000000", bg_color=TOTAL_BG,
                            align="right", border=1, shrink=True))
    # hudud qatorlari
    r1 = rj + 1
    for i, r in enumerate(rows):
        rr = r1 + i
        ws.set_row(rr, ROW_H * K)
        ws.write(rr, 0, r["name"], fmt(font_size=sz(8.5), border=1, indent=1))
        for g in range(NG):
            v = r["cur"].get(f"c{g}", 0)
            vf = fmt(bold=True, font_size=sz(VAL_SZ_D[g]), font_color=VAL_D[g], align="right", border=1, num_format="#,##0")
            if v:
                ws.write_number(rr, 1 + 2 * g, v, vf)
            else:
                ws.write_blank(rr, 1 + 2 * g, None, vf)
            dt = _delta_txt(r["cur"], r["base"], g)
            ws.write_string(rr, 2 + 2 * g, dt[0] if dt else "",
                            fmt(bold=True, font_size=sz(DLT_SZ_D[g]), font_color=dt[1] if dt else "#000000", align="right",
                                border=1, shrink=True))
    last = r1 + len(rows) - 1
    for g, colr in BAR.items():
        ws.conditional_format(r1, 1 + 2 * g, last, 1 + 2 * g,
                              {"type": "data_bar", "bar_color": colr, "bar_solid": True, "bar_no_border": True,
                               "min_type": "num", "min_value": 0, "max_type": "max"})
    ws.set_landscape()
    ws.set_paper(9)
    ws.fit_to_pages(1, 1)
    ws.set_margins(left=0.25, right=0.25, top=0.4, bottom=0.4)
    ws.center_horizontally()
    ws.print_area(0, 0, last, ncols - 1)
    wb.close()
    return buf.getvalue()
