"""Respublika dinamikasi: Qashqadaryo HETK PDF'idagi «Жами» (viloyat) qatorini o'qiydi.
PDF Excel'dan chiqarilgan: har bir sahifa — bitta jadval, birinchi ustun — hudud nomi.
Biz faqat viloyat jami qatorini (qiymat va PDF'dagi ↑↓ o'zgarishi) saqlaymiz."""
import io
import re
from datetime import date

import pdfplumber

JAMI = {"Жами", "Jami", "ЖАМИ", "JAMI"}
DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
RANGE_RE = re.compile(r"Динамика:\s*(\d{2}\.\d{2}\.\d{4})(?:\s*[-–—]\s*(\d{2}\.\d{2}\.\d{4}))?")


def _d(s: str) -> date:
    dd, mm, yy = s.split(".")
    return date(int(yy), int(mm), int(dd))


def _dd(vals, gap=1.5):
    out: list[float] = []
    for x in sorted(vals):
        if not out or x - out[-1] > gap:
            out.append(x)
    return out


def _join(words: list[dict]) -> str:
    """Katak so'zlarini birlashtiradi: kerning (≈0 oraliq) — yopishtiriladi, haqiqiy bo'shliq — ming ajratgich."""
    out, prev = "", None
    for w in sorted(words, key=lambda w: (round(w["top"] / 4), w["x0"])):
        if prev is not None and abs(w["top"] - prev["top"]) < 4:
            out += ("" if w["x0"] - prev["x1"] < 0.6 else " ") + w["text"]
        elif prev is not None:
            out += " " + w["text"]
        else:
            out = w["text"]
        prev = w
    return out.strip()


def _num(t: str) -> int | None:
    t = t.replace("\xa0", " ").strip()
    if not t or t == "-":
        return None
    t = t.replace(" ", "")
    return int(t) if re.fullmatch(r"-?\d+", t) else None


def _cell(t: str) -> dict:
    t = t.strip()
    if t[:1] in "↑↓":
        v = _num(t[1:].lstrip("- ").strip())
        return {"k": "d", "d": None if v is None else (1 if t[0] == "↑" else -1) * abs(v)}
    if t.endswith("%"):
        return {"k": "p", "p": t}
    return {"k": "v", "v": _num(t)}


def _grid(pg, ws):
    """Jadval to'rini (vertikal/gorizontal chiziqlar) topib, har bir qator uchun katak matnlarini qaytaradi."""
    xs = _dd([e["x0"] for e in pg.edges if e["orientation"] == "v" and e["bottom"] - e["top"] > 15 and e["x0"] > 0])
    xs = [x for x in xs if x <= pg.width + 1]
    keep = xs[:1]
    for x in xs[1:]:
        if x - keep[-1] >= 8:
            keep.append(x)
    xs = keep
    ys = _dd([e["top"] for e in pg.edges if e["orientation"] == "h" and e["x1"] - e["x0"] > 15])
    if len(xs) < 3 or len(ys) < 3:
        return [], xs
    rows = []
    for y0, y1 in zip(ys, ys[1:]):
        if y1 - y0 < 5:
            continue
        r = []
        for i in range(len(xs) - 1):
            cw = [w for w in ws if xs[i] - 0.5 <= (w["x0"] + w["x1"]) / 2 < xs[i + 1] + 0.5 and y0 - 0.5 <= (w["top"] + w["bottom"]) / 2 < y1 + 0.5]
            r.append(_join(cw))
        rows.append((y0, r))
    return rows, xs


def _build_rows(rows0, xs, ws) -> tuple[list[dict], list[dict]] | None:
    """Jami qatoridan boshlab: [(jami_katak), tumanlar]. Delta ustunlari oldingi son ustuniga biriktiriladi."""
    rows = [r for _, r in rows0]
    st = next((i for i, r in enumerate(rows) if r and r[0].strip() in JAMI), None)
    if st is None:
        return None
    ytop = rows0[st][0]
    arrows = [any(("↑" in w["text"] or "↓" in w["text"]) and w["bottom"] < ytop + 1
                  and xs[j] - 0.5 <= (w["x0"] + w["x1"]) / 2 < xs[j + 1] + 0.5 for w in ws)
              for j in range(1, len(xs) - 1)]
    body = [r for r in rows[st:] if r and r[0].strip()]
    ncol = max(len(r) for r in body)
    kinds = [[_cell(r[j]) if j < len(r) else {"k": "v", "v": None} for j in range(1, ncol)] for r in body]
    nj = ncol - 1
    is_delta = []
    for j in range(nj):
        col = [row[j] for row in kinds]
        has_d = any(c["k"] == "d" and c.get("d") is not None for c in col)
        has_v = any(c["k"] in ("v", "p") and (c.get("v") is not None or c.get("p")) for c in col)
        is_delta.append((has_d and not has_v) or (arrows[j] if j < len(arrows) else False) and not has_v)
    out = []
    for r, row in zip(body, kinds):
        cells: list[dict] = []
        for j, c in enumerate(row):
            if is_delta[j]:
                if cells and c.get("d") is not None:
                    cells[-1]["d"] = c["d"]
                continue
            cells.append({"v": c.get("v"), "p": c.get("p"), "d": None})
        out.append({"name": r[0].strip(), "cells": cells})
    return out[0]["cells"], out[1:]


def parse_pdf(data: bytes) -> dict:
    """Qaytaradi: {"start", "end", "pages": [{"n", "title", "cells": [Jami], "rows": [{name, cells}]}]}"""
    pages, start, end = [], None, None
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for pn, pg in enumerate(pdf.pages, 1):
            ws = pg.extract_words(x_tolerance=1.2)
            if not ws:
                continue
            txt = " ".join(w["text"] for w in sorted(ws, key=lambda w: (round(w["top"]), w["x0"])))
            m = RANGE_RE.search(txt)
            if m and not end:
                a, b = m.group(1), m.group(2)
                start, end = _d(a), _d(b) if b else None
                if not b:
                    d2 = DATE_RE.findall(txt)
                    end = _d(".".join(d2[0])) if d2 else None
            g, xs = _grid(pg, ws)
            got = _build_rows(g, xs, ws) if g else None
            if not got:
                continue
            jami, districts = got
            title = " ".join(w["text"] for w in sorted([w for w in ws if w["top"] < 40], key=lambda w: (round(w["top"]), w["x0"])))
            n = len(jami)
            pages.append({"n": pn, "title": title[:200],
                          "cells": [{"label": f"Ustun {i + 1}", **c} for i, c in enumerate(jami)],
                          "rows": [{"name": d["name"], "cells": d["cells"]} for d in districts if len(d["cells"]) == n]})
    return {"start": start, "end": end, "pages": pages}


PAGES = (1, 2, 3, 4, 6, 7, 8)
TITLES = {
    1: "Konsentratorlar holati",
    2: "Aloqaga chiqmagan hisoblagichlar",
    3: "Tarmoqdan uzilgan hisoblagichlar",
    4: "Balans hisoblagichlar va transformatorlar yuklamasi",
    6: "48 soat ichida obxod bergan hisoblagichlar",
    7: "Balans va iste'molchi hisoblagichlari o'rtasidagi tafovut",
    8: "Billing va CAS dasturlaridagi tafovutlar",
    9: "SmartApp orqali ma'lumot yuborilgan hisoblagichlar",
}
LABELS = {
    1: ["Dasturda mavjud transformatorlar", "CAS ga yuklangan", "Online", "Offline", "Shundan 3 kundan ortiq offline",
        "Obxod 0%", "Obxod 1-30%", "Obxod 30-50%", "Obxod 50-80%", "Obxod 80-100%", "Hisoblagichi biriktirilmagan"],
    2: ["Aloqaga chiqqan hisoblagichlar", "Aloqadan chiqib ketgan — jami", "%", "Aholi", "Ulgurji", "Balans",
        "7-30 kun", "1-3 oy", "3 oydan ortiq", "Billingda otkl. status"],
    3: ["Aloqaga chiqqan hisoblagichlar", "Tarmoqdan uzilgan — jami", "%", "4-7 kun", "7-30 kun", "30 kundan ortiq",
        "To'g'ridan-to'g'ri ulanish (peremichka)"],
    4: ["Loyiha doirasida", "CAS ga yuklangan", "Bir marta obxod olgan", "Umuman obxod olmagan",
        "3 kundan ortiq obxod olmagan", "Muammoli transformatorlar", "Quvvati kiritilmagan",
        "TT noto'g'ri yoki nominali xato", "Sxema xato yoki cos=0", "Balans hisoblagich aloqaga chiqmagan",
        "TP yuklamasi 0%", "TP yuklamasi 150%"],
    6: ["Jami hisoblagichlar", "Shundan obxod olgan", "%", "Aholi — jami", "Aholi — obxod olgan", "%",
        "Ulgurji — jami", "Ulgurji — obxod olgan", "%", "Balans — jami", "Balans — obxod olgan", "%"],
    7: ["Dasturdagi transformatorlar", "Shundan rezervda", "Balans hisoblagich o'rnatilgan TP", "Manfiy tafovut",
        "Tafovut 0%", "Tafovut 1-10%", "Tafovut 10-20%", "Tafovut 20-50%", "Tafovut 50-100%"],
    8: ["Billing bilan ma'lumot almashmaydigan — jami", "Istemolchi hisob raqami mos emas", "Istemolchi turi mos emas",
        "CAS da mavjud bo'lmagan", "ASKUE ga mos bo'lmagan", "Shundan aholi", "Shundan ulgurji", "Dublikat hisoblagichlar",
        "CAS da bor, Billingga kiritilmagan", "Shundan 3 kunda obxod olgan", "Shundan 30 kunda obxod olgan"],
    9: ["Obxod olmagan hisoblagichlar", "SmartApp orqali yuborilgan — jami", "Oy boshidan", "{d0}", "{d1}", "{d2}",
        "{d3}", "{d4}", "{d5}", "{d6}", "O'tgan oyda"],
}


# Sahifa tuzilishi PDF versiyasiga qarab o'zgargan bo'lishi mumkin: 2-sahifaga oxirida «Billingda otkl. status»
# ustuni qo'shilgan (yangi PDF'larda 10 ta katak, eskilarida 9 ta). Yangi ustun doim OXIRGI — shuning uchun
# eski va yangi PDF'ni birinchi 9 ta katak bo'yicha solishtirish mumkin.
VARIANTS = {2: {9: "old", 10: "new"}}
COMPAT = {2: {9, 10}}
# PDF'ning o'zida ↑↓ si BO'LMAGAN kataklar (sahifa -> katak raqamlari): ularning farqi serverda hisoblanadi —
# kunlik rejimda tanlangan ikki sana o'rtasidagi, oy boshidan rejimda esa oy boshi sanasi PDF'iga nisbatan.
NO_PDF_DELTA = {2: {9}}


def comparable(page: int, a: int, b: int) -> bool:
    """Ikki PDF'dagi sahifa kataklarini tartib raqami bo'yicha solishtirish mumkinmi."""
    return a == b or (a in COMPAT.get(page, ()) and b in COMPAT.get(page, ()))


def label_for(page: int, idx: int, count: int, end: date | None, fallback: str) -> str:
    lab = LABELS.get(page)
    if lab and page in VARIANTS and count in VARIANTS[page]:
        lab = lab[:count]                     # eski variant: oxirgi (yangi) ustun yo'q
    if not lab or len(lab) != count:
        return fallback
    t = lab[idx]
    if t.startswith("{d") and end:
        from datetime import timedelta
        d = end - timedelta(days=int(t[2:-1]))
        return d.strftime("%d.%m")
    return t


def parse_report(data: bytes) -> dict:
    """parse_pdf + lotincha sarlavha va ustun nomlari. Faqat 1,2,3,4,6,7,8-sahifalar."""
    r = parse_pdf(data)
    out = []
    for p in r["pages"]:
        if p["n"] not in PAGES:
            continue
        n = len(p["cells"])
        cells = []
        for i, c in enumerate(p["cells"]):
            cells.append({"label": label_for(p["n"], i, n, r["end"], c["label"]), "v": c["v"], "p": c["p"], "d": c["d"]})
        out.append({"n": p["n"], "title": TITLES.get(p["n"], p["title"]), "cells": cells, "rows": p.get("rows", [])})
    r["pages"] = out
    return r


def page_values(cells: list[dict], other: list[dict] | None, strict: bool = False,
                ref: list[dict] | None = None, nod: frozenset | set = frozenset()) -> tuple[dict, dict]:
    """Sahifa katak ro'yxatidan (cur, base) lug'atlari. PDF'dagi ↑↓ foiz katagidan keyin turadi — u oldingi
    sonli katakka tegishli.

    strict=False (oy boshidan): dinamika PDF'ning o'z ↑↓ qiymatlaridan olinadi (oy boshiga nisbatan).
    strict=True  (kunlik): dinamika = joriy son − `other` (tanlangan boshqa sana) soni. `other` yo'q bo'lsa
    dinamika bo'sh qoladi — PDF'ning oy boshidagi ↑↓ qiymati kunlik farq sifatida ko'rsatilmaydi."""
    n = len(cells)
    d = [c.get("d") for c in cells]
    for i, c in enumerate(cells):
        if c.get("p") and d[i] is not None and i > 0:
            if d[i - 1] is None:
                d[i - 1] = d[i]
            d[i] = None
    cur, base = {}, {}
    for i, c in enumerate(cells):
        v = c.get("v") or 0
        cur[f"c{i}"] = v
        if c.get("p"):
            cur[f"t{i}"] = c["p"]
        if strict:
            # yangi ustun (eski PDF'da yo'q) yoki `other` topilmasa — farq yo'q (base = cur)
            base[f"c{i}"] = (other[i].get("v") or 0) if other is not None and i < len(other) else v
        elif i in nod:
            # PDF'da ↑↓ yo'q: oy boshi sanasidagi PDF'ning shu katagiga nisbatan (u yo'q bo'lsa — farqsiz)
            base[f"c{i}"] = (ref[i].get("v") or 0) if ref is not None and i < len(ref) else v
        else:
            base[f"c{i}"] = v - (d[i] or 0)
    return cur, base


def spec_json(key: str) -> dict:
    from . import report_spec as S
    cfg = S.TABLES[key]
    head = [[{"l": S.plain(l), "rs": rs, "cs": cs, "c": c} for (l, rs, cs, c) in row] for row in cfg["head"]]
    cols = []
    for c in cfg["cols"]:
        if c[0] == "n":
            cols.append({"t": "n", "m": c[1], "cls": c[2]})
        elif c[0] == "d":
            cols.append({"t": "d", "m": c[1], "pol": c[2]})
        else:
            cols.append({"t": "t", "m": c[1]})
    return {"title": cfg["title"], "short": cfg["short"], "head": head, "cols": cols}


def _fmt(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def compare(a: dict | None, b: dict, base_iso: str, to_iso: str, ref: list[tuple[str, dict]] | None = None) -> list[dict]:
    """Har sahifa: spetsifikatsiya + viloyat jami qatori (cur) va solishtirish (base).

    a berilsa (kunlik) — farq = b sanasi − a sanasi (har ikkala PDF'ning o'z sonlari). a yo'q bo'lsa — PDF'ning
    oy boshiga nisbatan ↑↓ qiymatlari; PDF'da ↑↓ si yo'q kataklar (NO_PDF_DELTA) uchun — `ref` ro'yxatidagi
    [(sana, PDF ma'lumoti)] (oy boshidan b gacha yuklangan sanalar, eskisidan boshlab) dan shu ustun bor eng birinchisi
    bilan solishtiriladi (odatda oy boshi PDF'i)."""
    from . import report_spec as S
    pa = {p["n"]: p for p in (a or {}).get("pages", [])}
    strict = a is not None
    res = []
    for p in b["pages"]:
        if p["n"] not in S.REPUBLIC:
            continue
        key = S.republic_key(p["n"], len(p["cells"]))
        old = pa.get(p["n"]) if strict else None
        warn = ""
        if strict and (old is None or not comparable(p["n"], len(old["cells"]), len(p["cells"]))):
            warn = "Bu sahifa tanlangan sanalar PDF'larida har xil tuzilgan — farqni hisoblab bo'lmadi"
            old = None
        nod = {i for i in NO_PDF_DELTA.get(p["n"], ()) if i < len(p["cells"])}
        rp = None
        if nod and not strict:
            for r_iso, r_data in ref or []:
                x = next((x for x in r_data.get("pages", []) if x["n"] == p["n"]), None)
                if x is not None and len(x["cells"]) > max(nod):
                    rp, ref_iso = x, r_iso
                    break
            if rp is None:
                warn = ("«Billingda otkl. status» farqini hisoblash uchun oy boshidan shu sanagacha yangi formatdagi "
                        "boshqa PDF yuklanmagan — bu ustunda farq ko'rsatilmaydi")
            elif ref_iso != base_iso:
                warn = (f"«Billingda otkl. status» farqi {_fmt(ref_iso)} sanasiga nisbatan (oy boshi "
                        f"{_fmt(base_iso)} PDF'ida bu ustun yo'q)")
        cur, base = page_values(p["cells"], old["cells"] if old else None, strict, rp["cells"] if rp else None, nod)
        old_rows = {r["name"]: r["cells"] for r in (old or {}).get("rows", [])}
        ref_rows = {r["name"]: r["cells"] for r in (rp or {}).get("rows", [])}
        rows = []
        for i, r in enumerate(p.get("rows", [])):
            rc, rb = page_values(r["cells"], old_rows.get(r["name"]), strict, ref_rows.get(r["name"]), nod)
            rows.append({"id": i + 1, "name": r["name"], "cur": rc, "base": rb})
        res.append({"n": p["n"], "key": key, **spec_json(key), "cur": cur, "base": base, "rows": rows,
                    "to": to_iso, "from": base_iso, "warn": warn})
    return res
