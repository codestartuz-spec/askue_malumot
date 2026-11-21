"""AG (Aloqadan chiqib ketgan va hodisalar) dinamikasi: «Farq: 20.02.2023 - 17.11.2026» PDF'ini o'qiydi.

PDF — bitta sahifa, bitta jadval: Hudud + 9 ta guruh (har biri «son» va «↑↓ o'zgarish» katagi). O'zgarish
(↑↓) PDF'dagi boshlang'ich sana (odatda 20.02.2023) bilan farq. Kunlik rejimda esa ikki yuklangan PDF
qiymatlari o'zaro solishtiriladi (Respublika dinamikasidagi kabi)."""
import io
import re
from datetime import date

import pdfplumber

from .republic import JAMI, _cell, _d, _join, _num

FARQ_RE = re.compile(r"Farq:\s*(\d{2}\.\d{2}\.\d{4})\s*[-–—]\s*(\d{2}\.\d{2}\.\d{4})")
DEFAULT_TITLE = "24.02.2023 dagi № 01-04-42-22 sonli topshiriq ijrosi bo'yicha"
DEFAULT_REGION = "Qashqadaryo HETK"
NG = 9                                        # guruhlar soni

# Guruhlar: (kalit, qisqa nom). Kalit — c0..c8.
GROUPS = [
    "Kirish va chiqish quvvati orasidagi nomutanosiblik",
    "Hisoblagich qutisi ochilgan",
    "Klemmasi ochilgan",
    "Kuchlanishsiz tok oqib o'tayotgan",
    "Aloqadan chiqib ketgan — jami",
    "Aloqadan chiqib ketgan — 1-3 oy",
    "Aloqadan chiqib ketgan — 3 oydan ortiq",
    "Kirish va chiqish simlari tutashtirilgan (peremichka)",
    "Aloqaga chiqmagan hisoblagichlar",
]


def _lines_xy(pg):
    """Jadval chiziqlari: (gorizontal y'lar, vertikal x'lar). Avval haqiqiy chiziqlar, bo'lmasa — qirralar."""
    src = pg.lines or [e for e in pg.edges if e.get("object_type") == "line"] or pg.edges
    ys = sorted({round(l["top"], 1) for l in src if abs(l["top"] - l["bottom"]) < 0.6 and l["x1"] - l["x0"] > 15})
    xs = sorted({round(l["x0"], 1) for l in src if abs(l["x0"] - l["x1"]) < 0.6 and l["bottom"] - l["top"] > 10})

    def dedupe(v, gap):
        out: list[float] = []
        for a in v:
            if not out or a - out[-1] > gap:
                out.append(a)
        return out
    return dedupe(ys, 1.0), dedupe(xs, 1.5)


def looks_like_ag(data: bytes) -> bool:
    """PDF AG hisobotimi (sarlavhasida «Farq: …» va «topshiriq» bor)?"""
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            txt = " ".join((pg.extract_text() or "") for pg in pdf.pages[:2])
    except Exception:  # noqa: BLE001
        return False
    return bool(FARQ_RE.search(txt)) and "topshiriq" in txt


def parse_pdf(data: bytes) -> dict:
    """Qaytaradi: {"start","end","title","region","total":[9 katak],"rows":[{"name","cells":[9 katak]}]}.
    Katak: {"v": son|None, "d": o'zgarish|None}."""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pg = pdf.pages[0]
        ws = pg.extract_words(x_tolerance=1.2)
        txt = " ".join(w["text"] for w in sorted(ws, key=lambda w: (round(w["top"]), w["x0"])))
        m = FARQ_RE.search(txt)
        if not m:
            raise ValueError("«Farq: …» sanasi topilmadi")
        start, end = _d(m.group(1)), _d(m.group(2))
        ys, xs = _lines_xy(pg)
        if len(xs) < 2 + 2 * NG:
            raise ValueError("jadval ustunlari topilmadi")
        xs = xs[:2 + 2 * NG] if len(xs) > 2 + 2 * NG else xs
        jami = next((w for w in ws if w["text"] in JAMI and w["x0"] < xs[1]), None)
        if not jami:
            raise ValueError("«Jami» qatori topilmadi")
        cy = (jami["top"] + jami["bottom"]) / 2
        body_ys = [y for y in ys if y >= 100]
        st = max((i for i, y in enumerate(body_ys) if y <= cy), default=None)
        if st is None:
            raise ValueError("«Jami» qatori topilmadi")
        bounds = body_ys[st:]
        rows = []
        for y0, y1 in zip(bounds, bounds[1:]):
            if y1 - y0 < 5:
                continue
            cells = []
            for i in range(len(xs) - 1):
                cw = [w for w in ws if xs[i] - 0.5 <= (w["x0"] + w["x1"]) / 2 < xs[i + 1] + 0.5
                      and y0 - 0.5 <= (w["top"] + w["bottom"]) / 2 < y1 + 0.5]
                cells.append(_join(cw))
            rows.append(cells)
        title_w = [w for w in ws if 25 < w["top"] < 46]
        title = _join(title_w) if title_w else DEFAULT_TITLE
        bx = [w for w in ws if w["text"] == "Nomi:" and 60 < w["top"] < 82]
        x_from = (bx[0]["x1"] + 8) if bx else xs[1] + 30
        region_w = [w for w in ws if 62 < w["top"] < 80 and w["x0"] > x_from and w["x1"] < x_from + 150 and w["text"].lower() != "farq:"]
        region = _join(region_w) if region_w else DEFAULT_REGION
    out = []
    for r in rows:
        if not r or not r[0].strip():
            continue
        cells = []
        for g in range(NG):
            v = _cell(r[1 + 2 * g]) if 1 + 2 * g < len(r) else {"v": None}
            d = _cell(r[2 + 2 * g]) if 2 + 2 * g < len(r) else {"d": None}
            cells.append({"v": v.get("v"), "d": d.get("d") if d.get("k") == "d" else None})
        out.append({"name": r[0].strip(), "cells": cells})
    if not out or out[0]["name"] not in JAMI:
        raise ValueError("«Jami» qatori topilmadi")
    if len(out) < 2:
        raise ValueError("hudud qatorlari topilmadi")
    return {"start": start, "end": end, "title": title or DEFAULT_TITLE, "region": region or DEFAULT_REGION,
            "total": out[0]["cells"], "rows": out[1:]}


def _vals(cells: list[dict], other: list[dict] | None) -> tuple[dict, dict]:
    """Katak ro'yxatidan (cur, base): base — PDF'dagi o'zgarish (v - d) yoki boshqa sana qiymati."""
    cur, base = {}, {}
    for i, c in enumerate(cells):
        v = c.get("v") or 0
        cur[f"c{i}"] = v
        base[f"c{i}"] = (other[i].get("v") or 0) if other is not None and i < len(other) else v - (c.get("d") or 0)
    return cur, base


def compare(a: dict | None, b: dict, base_iso: str, to_iso: str) -> dict:
    """b — joriy (oxirgi sana) ma'lumoti, a — solishtiriladigan oldingi PDF (kunlik rejim) yoki None (boshidan)."""
    cur, base = _vals(b["total"], a["total"] if a else None)
    old = {r["name"]: r["cells"] for r in (a or {}).get("rows", [])}
    rows = []
    for i, r in enumerate(b["rows"]):
        rc, rb = _vals(r["cells"], old.get(r["name"]) if a else None)
        rows.append({"id": i + 1, "name": r["name"], "cur": rc, "base": rb})
    from ..settings_store import app_cfg
    return {"title": b.get("title") or app_cfg("ag_title"), "region": b.get("region") or app_cfg("ag_region"),
            "cur": cur, "base": base, "rows": rows, "from": base_iso, "to": to_iso}


def to_date(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None
