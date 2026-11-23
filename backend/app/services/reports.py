"""Dinamika hisobotlari: Excel va PDF."""
import html
import io
from datetime import date

import xlsxwriter
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from ..config import BASE
from . import report_spec as S

_FONTS = BASE / "assets" / "fonts"
_registered = False


def _fonts() -> None:
    global _registered
    if not _registered:
        for name, f in (("CA", "Carlito-Regular"), ("CA-B", "Carlito-Bold"), ("CA-I", "Carlito-Italic"),
                        ("CA-BI", "Carlito-BoldItalic")):
            pdfmetrics.registerFont(TTFont(name, str(_FONTS / f"{f}.ttf")))
        _registered = True


def dmy(iso: str | None) -> str:
    return ".".join(reversed(iso.split("-"))) if iso else ""


def period(data: dict) -> str:
    if data.get("base"):
        return f"{dmy(data['base'])} – {dmy(data['to'])}"
    return dmy(data.get("to"))


def title_of(table: str, scope: str) -> str:
    return f"{scope} {S.TABLES[table]['title']}"


def _body_rows(data: dict):
    """[(nom, cur, base, is_total)] — birinchi qator 'Jami'."""
    tot = data["total"]
    rows = [("Jami", tot["cur"], tot["base"], True)]
    rows += [(r["name"] + ("\n" + ", ".join(r["members"]) if r.get("members") else ""), r["cur"], r["base"], False)
             for r in data["rows"]]
    return rows


# --------------------------------------------------------------------- yordamchi
def _segments(label: str) -> list[list[tuple[str, str | None]]]:
    """«A\n{ko'k} [qizil] B» → qatorlar ro'yxati: [[(matn, rang|None), ...], ...]."""
    out = []
    for ln in label.split("\n"):
        seg, buf, col = [], "", None
        for ch in ln:
            if ch in "{[":
                if buf:
                    seg.append((buf, col))
                buf, col = "", "#4472C4" if ch == "{" else "#C00000"
            elif ch in "}]":
                if buf:
                    seg.append((buf, col))
                buf, col = "", None
            else:
                buf += ch
        if buf:
            seg.append((buf, col))
        out.append(seg)
    return out


def _plain(label: str) -> str:
    for ch in "{}[]":
        label = label.replace(ch, "")
    return label


def _split_delta(txt: str) -> tuple[str, str]:
    return txt[0], txt[1:]


def _cream(table: str, j: int, total: bool) -> bool:
    return (not total) and j in S.CREAM_COLS.get(table, ())


def _pink(table: str, col, cur: dict, total: bool) -> bool:
    if total or table not in S.PINK_TABLES or col[0] != "p":
        return False
    a, b = cur.get(col[1], 0), cur.get(col[2], 0)
    return b > 0 and a / b * 100 < 90


def _head_tint(table: str, cls: str):
    if table in S.PINK_TABLES:
        for k in ("green", "amber", "purple"):
            if k in (cls or "").split():
                return S.TINT[k]
    return None


# --------------------------------------------------------------------- Excel
K = 1.45          # PDF (pt) → Excel (pt): asl hisobotda ~69% masshtab


def build_xlsx(items: list[tuple[str, dict]], scope: str, first_col: str) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    fcache: dict = {}

    def fmt(**kw):
        key = tuple(sorted(kw.items()))
        if key not in fcache:
            fcache[key] = wb.add_format({"font_name": "Calibri", "font_size": 11, "valign": "vcenter", **kw})
        return fcache[key]

    for table, data in items:
        cfg = S.TABLES[table]
        ws = wb.add_worksheet(cfg["short"][:30])
        ws.hide_gridlines(2)
        ncols = 1 + len(cfg["cols"])
        rows_b = _body_rows(data)
        has_mem = any("\n" in b[0] for b in rows_b)
        ws.merge_range(0, 0, 0, ncols - 1, title_of(table, scope), fmt(bold=True, font_size=18, align="center"))
        ws.merge_range(1, 0, 1, ncols - 1, "D I N A M I K A", fmt(bold=True, font_size=18, align="center", font_color="#FF0000"))
        ws.write(2, 0, "Hudud nomi:", fmt(align="right", font_size=14))
        ws.merge_range(2, 1, 2, 3, scope, fmt(bold=True, font_color="#0066FF", border=1, border_color="#00B0F0", align="left", font_size=14))
        ws.merge_range(2, max(ncols - 6, 5), 2, ncols - 1, f"Dinamika: {period(data)}",
                       fmt(bold=True, font_color="#0000FF", align="right", font_size=14))
        ws.set_row(0, 24)
        ws.set_row(1, 24)
        ws.set_row(2, 22)
        top = 4
        heads = [[(l if l != "Hudud nomi" else first_col, rs, cs, c) for (l, rs, cs, c) in row] for row in cfg["head"]]
        hh = S.head_heights(table, len(heads))
        for r, h in enumerate(hh):
            ws.set_row(top + r, h * K)
        for r, c, rs, cs, label, cls in S.place_header(heads, ncols):
            st = S.head_style(cls)
            tint = _head_tint(table, cls)
            kw = dict(bold=True, font_color=st["color"], bg_color=tint or S.HEAD_BG, align="center", text_wrap=True,
                      border=1, italic=st["it"], font_size=9 if st["small"] else 13)
            if st["vert"]:
                kw.update(rotation=90, font_size=9 if st["small"] else 10)
            if label == first_col:
                kw["font_size"] = 18
            f = fmt(**kw)
            rich = st["arr"]
            segs = _segments(label)
            mixed = any(c2 for ln in segs for _, c2 in ln)

            def put(rr, cc):
                if rich:
                    ws.write_rich_string(rr, cc, fmt(font_color="#0066FF", bold=True, font_size=12), "↑ ",
                                         fmt(font_color="#FF0000", bold=True, font_size=12), "↓", f)
                elif mixed:
                    parts = []
                    for li, ln in enumerate(segs):
                        for k2, (tx, col2) in enumerate(ln):
                            parts += [fmt(bold=True, font_size=13, font_color=col2 or "#000000"),
                                      tx + ("\n" if li < len(segs) - 1 and k2 == len(ln) - 1 else "")]
                    ws.write_rich_string(rr, cc, *parts, f)
                else:
                    ws.write(rr, cc, _plain(label), f)

            if rs == 1 and cs == 1:
                put(top + r, c)
            else:
                ws.merge_range(top + r, c, top + r + rs - 1, c + cs - 1, "", f)
                put(top + r, c)
        start = top + len(cfg["head"])
        for i, (name, cur, base, total) in enumerate(rows_b):
            bg = S.TOTAL_BG if total else "#FFFFFF"
            nm = name.split("\n")[0]
            ws.write(start + i, 0, name if "\n" in name else nm,
                     fmt(bold=total, bg_color=bg, border=1, align="center" if total else "left",
                         font_size=13 if total else 11, text_wrap=True, indent=0 if total else 0))
            if total:
                ws.set_row(start + i, S.TOTAL_H * K)
            elif "\n" in name:
                ws.set_row(start + i, S.ROW_H * K + 11 * (1 + -(-len(name.split(chr(10))[1]) // 40)))
            else:
                ws.set_row(start + i, S.ROW_H * K)
            for j, col in enumerate(cfg["cols"], start=1):
                txt, color, bold = S.cell_values(col, cur, base)
                cbg = bg
                if _cream(table, j, total):
                    cbg = S.CREAM
                elif _pink(table, col, cur, total):
                    cbg = S.PINK
                kw = dict(bg_color=cbg, border=1, align="right" if col[0] != "d" else "right", bold=bold or total,
                          font_size=12 if total else 11)
                if col[0] == "d":
                    if txt:
                        arrow, num = _split_delta(txt)
                        ac = S.ARROW_COL.get(color, "#000000")
                        ws.write_rich_string(start + i, j, fmt(font_color=ac, bold=True, font_size=12), arrow,
                                             fmt(font_color=ac, bold=True, font_size=8), num, fmt(**kw))
                    else:
                        ws.write(start + i, j, "", fmt(**kw))
                    continue
                if color:
                    kw["font_color"] = S.COLORS.get(color, "#000000")
                if col[0] == "n" and txt:
                    ws.write_number(start + i, j, int(cur.get(col[1], 0)), fmt(**kw, num_format="#,##0"))
                else:
                    ws.write(start + i, j, txt, fmt(**kw))
        # ustun kengliklari (asl: son 41.2pt, dinamika 32pt)
        ws.set_column(0, 0, 26 if has_mem else 22)
        for j, col in enumerate(cfg["cols"], start=1):
            ws.set_column(j, j, 8.3 if col[0] == "d" else 10.7)
        ws.freeze_panes(start, 1)
        ws.set_landscape()
        ws.fit_to_pages(1, 0)
        ws.set_paper(1)
        ws.center_horizontally()
    wb.close()
    return buf.getvalue()


# ----------------------------------------------------------------------- PDF
def _hex(c: str):
    return colors.HexColor(c)


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    out, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if stringWidth(t, font, size) <= width or not cur:
            cur = t
        else:
            out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out or [""]


def _text_block(c, x, y, w, h, label, st, size, tint_color=None, rot=False):
    """Katak ichida matnni markazlab (yoki 90° burib) chizadi."""
    segs = _segments(label)
    font = "CA-BI" if st["it"] else "CA-B"
    base = _hex(st["color"])
    if rot:
        c.saveState()
        c.translate(x + w / 2, y + h / 2)
        c.rotate(90)
        lim = h - 4
        lines = []
        for ln in segs:
            lines += _wrap("".join(t for t, _ in ln), font, size, lim)
        lead = size * 1.12
        c.setFillColor(base)
        c.setFont(font, size)
        for i, ln in enumerate(lines):
            c.drawCentredString(0, ((len(lines) - 1) / 2 - i) * lead - size * 0.32, ln)
        c.restoreState()
        return
    while True:
        lead = size * 1.18
        lines = []   # [(segments)]
        for ln in segs:
            plain = "".join(t for t, _ in ln)
            if stringWidth(plain, font, size) <= w - 3 or len(ln) > 1:
                lines.append(ln)
            else:
                lines += [[(t, ln[0][1] if ln else None)] for t in _wrap(plain, font, size, w - 3)]
        fits = len(lines) * lead <= h - 2 and all(
            stringWidth("".join(t for t, _ in ln), font, size) <= w - 2 for ln in lines)
        if fits or size <= 5:
            break
        size -= 0.3
    n = len(lines)
    for i, ln in enumerate(lines):
        total = sum(stringWidth(t, font, size) for t, _ in ln)
        cx = x + w / 2 - total / 2
        yy = y + h / 2 + ((n - 1) / 2 - i) * lead - size * 0.32
        for t, col in ln:
            c.setFillColor(_hex(col) if col else base)
            c.setFont(font, size)
            c.drawString(cx, yy, t)
            cx += stringWidth(t, font, size)


def _page(c, table, data, scope, first_col):
    cfg = S.TABLES[table]
    cols = cfg["cols"]
    ncols = 1 + len(cols)
    rows_b = _body_rows(data)
    heads = [[(l if l != "Hudud nomi" else first_col, rs, cs, cl) for (l, rs, cs, cl) in row] for row in cfg["head"]]
    hh = S.head_heights(table, len(heads))
    has_mem = any("\n" in b[0] for b in rows_b)
    name_w = 112.0 if has_mem else 85.1
    wt = [41.2 if k[0] == "n" else 31.7 if k[0] == "d" else 30.0 for k in cols]
    scale = (S.TBL_W - name_w) / sum(wt)
    xs = [S.TBL_X, S.TBL_X + name_w]
    for w in wt:
        xs.append(xs[-1] + w * scale)
    # qator balandliklari; ko'p qator bo'lsa siqamiz
    body = rows_b[1:]
    mem_h = {}
    for i, (name, *_r) in enumerate(body, start=1):
        if "\n" in name:
            mem = name.split("\n", 1)[1]
            nl = len(_wrap(mem, "CA", 5.6, name_w - 7))
            mem_h[i] = 12.2 + nl * 6.4
    fixed = sum(hh) + S.TOTAL_H + sum(mem_h.values())
    n_norm = len(body) - len(mem_h)
    title_block = 55.9
    avail = S.PAGE_H - 24 - 30 - title_block
    k = min(1.0, (avail - fixed) / (n_norm * S.ROW_H)) if n_norm else 1.0
    row_h = max(S.ROW_H * k, 8.5)
    f = min(1.0, row_h / S.ROW_H)
    block = title_block + fixed + n_norm * row_h
    T = min(109.8, S.PAGE_H - 24 - block)
    T = max(T, 24)
    ytop = lambda t: S.PAGE_H - t   # noqa: E731  (yuqoridan → pastdan koordinata)

    # sarlavha
    c.setFillColor(colors.black)
    c.setFont("CA-B", 12.4)
    c.drawCentredString(S.PAGE_W / 2, ytop(T + 11.2), title_of(table, scope))
    c.setFillColor(_hex("#FF0000"))
    c.drawCentredString(S.PAGE_W / 2, ytop(T + 34.6), "D  I  N  A  M  I  K  A")
    # hudud nomi / davr
    iy = T + 35.5
    c.setFillColor(colors.black)
    c.setFont("CA", 9.6)
    c.drawString(48.1, ytop(iy + 10.6), "Hudud nomi:")
    c.setStrokeColor(_hex("#00B0F0"))
    c.setLineWidth(0.8)
    c.rect(123.9, ytop(iy + 14.8), 123.8, 14.8)
    c.setFillColor(_hex("#0066FF"))
    c.setFont("CA-B", 9.6)
    c.drawString(126.4, ytop(iy + 10.6), scope)
    c.setFillColor(_hex("#0000FF"))
    c.drawRightString(S.TBL_X + S.TBL_W - 1.5, ytop(iy + 10.6), f"Dinamika: {period(data)}")

    y0 = T + title_block              # jadval tepasi
    # sarlavha katak chegaralari
    ycum = [y0]
    for h in hh:
        ycum.append(ycum[-1] + h)
    cells = S.place_header(heads, ncols)
    # 1) to'ldirish
    for r, cc, rs, cs, label, cls in cells:
        st = S.head_style(cls)
        x, w = xs[cc], xs[cc + cs] - xs[cc]
        yb, hgt = ytop(ycum[r + rs]), ycum[r + rs] - ycum[r]
        c.setFillColor(_hex(_head_tint(table, cls) or S.HEAD_BG))
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.45)
        c.rect(x, yb, w, hgt, fill=1, stroke=1)
    # 2) matn
    for r, cc, rs, cs, label, cls in cells:
        st = S.head_style(cls)
        x, w = xs[cc], xs[cc + cs] - xs[cc]
        yb, hgt = ytop(ycum[r + rs]), ycum[r + rs] - ycum[r]
        if st["arr"]:
            c.setFont("CA-B", 7.6)
            wa = stringWidth("↑ ", "CA-B", 7.6) + stringWidth("↓", "CA-B", 7.6)
            cx = x + w / 2 - wa / 2
            c.setFillColor(_hex("#0066FF"))
            c.drawString(cx, yb + hgt / 2 - 2.5, "↑ ")
            c.setFillColor(_hex("#FF0000"))
            c.drawString(cx + stringWidth("↑ ", "CA-B", 7.6), yb + hgt / 2 - 2.5, "↓")
            continue
        if label == first_col:
            size = 12.4
        elif st["vert"]:
            size = 6.2 if st["small"] else 7.6
        elif st["small"]:
            size = 6.2
        elif rs * cs == 1 or (rs == 1 and cs <= 2) or r > 0:
            size = 7.6 if r > 0 else 8.3
        else:
            size = 9.6
        if r == 0 and cs >= 5 and not st["vert"]:
            size = 8.3 if cs < 10 else 7.6
            size = 9.6 if label.split("\n")[0].startswith(("Konsentratorlar", "Jami ")) and cs == 5 else size
        _text_block(c, x, yb, w, hgt, label, st, size, rot=st["vert"])

    # tana
    ycur = y0 + sum(hh)
    for i, (name, cur, base, total) in enumerate(rows_b):
        rh = S.TOTAL_H if total else mem_h.get(i, row_h)
        yb = ytop(ycur + rh)
        bg = S.TOTAL_BG if total else "#FFFFFF"
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.45)
        c.setFillColor(_hex(bg))
        c.rect(xs[0], yb, name_w, rh, fill=1, stroke=1)
        nm = name.split("\n")[0]
        if total:
            c.setFillColor(colors.black)
            c.setFont("CA-B", 9.6)
            c.drawCentredString(xs[0] + name_w / 2, yb + rh / 2 - 3.1, nm)
        else:
            c.setFillColor(colors.black)
            c.setFont("CA", 7.6 * f)
            if "\n" in name:
                mem = name.split("\n", 1)[1]
                c.drawString(xs[0] + 4, yb + rh - 8.6, nm)
                c.setFillColor(_hex("#475569"))
                c.setFont("CA", 5.6)
                for k2, ln in enumerate(_wrap(mem, "CA", 5.6, name_w - 7)):
                    c.drawString(xs[0] + 4, yb + rh - 15.5 - k2 * 6.4, ln)
            else:
                c.drawString(xs[0] + 4, yb + rh / 2 - 2.5 * f, nm)
        for j, col in enumerate(cols, start=1):
            x, w = xs[j], xs[j + 1] - xs[j]
            cbg = bg
            if _cream(table, j, total):
                cbg = S.CREAM
            elif _pink(table, col, cur, total):
                cbg = S.PINK
            c.setFillColor(_hex(cbg))
            c.rect(x, yb, w, rh, fill=1, stroke=1)
            txt, color, bold = S.cell_values(col, cur, base)
            if not txt:
                continue
            ty = yb + rh / 2 - (3.0 if total else 2.5) * f
            if col[0] == "d":
                arrow, num = _split_delta(txt)
                ac = _hex(S.ARROW_COL.get(color, "#000000"))
                sz = 6.2 * (1.25 if total else 1.0)
                wd = stringWidth(arrow, "CA-B", sz * 1.2) + stringWidth(num, "CA-B", sz)
                cx = x + w - 3.2 - wd
                c.setFillColor(ac)
                c.setFont("CA-B", sz * 1.2)
                c.drawString(cx, ty, arrow)
                c.setFont("CA-B", sz)
                c.drawString(cx + stringWidth(arrow, "CA-B", sz * 1.2), ty, num)
                continue
            c.setFillColor(_hex(S.COLORS.get(color, "#000000")) if color else colors.black)
            c.setFont("CA-B" if (bold or total or col[0] != "t") else "CA", (8.3 if total else 7.6) * f)
            c.drawRightString(x + w - 3.5, ty, txt)
        ycur += rh
    # tashqi ramka
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.9)
    c.rect(S.TBL_X, ytop(ycur), S.TBL_W, ycur - y0, fill=0, stroke=1)


def build_pdf(items: list[tuple[str, dict]], scope: str, first_col: str) -> bytes:
    _fonts()
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(S.PAGE_W, S.PAGE_H), pageCompression=1)
    c.setTitle("ASKUE ma'lumot — dinamika")
    c.setAuthor("ASKUE ma'lumot")
    for table, data in items:
        _page(c, table, data, scope, first_col)
        c.showPage()
    c.save()
    return buf.getvalue()
