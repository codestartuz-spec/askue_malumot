"""Respublika dinamikasi (barcha viloyatlar): R-Dynamic PDF'ni o'qish.

PDF jadvali chiziqlar bilan emas, fon to'rtburchaklari bilan chizilgan, shuning uchun kataklar matn joylashuvi
bo'yicha topiladi: «Жами» qatoridagi qiymatlar ustun markazlarini beradi, qolgan qatorlar shularga biriktiriladi.
Sahifalar: 1,2,3,4,6,7,9 (9-sahifa — Billing va CAS; Qashqadaryo jadvallari bilan bir xil ichki raqam 8 ostida
saqlanadi). 5-sahifa (diagramma) va 8-sahifa (SmartApp) o'tkazib yuboriladi."""
import io
import re

import pdfplumber

from . import republic as R

NUM = re.compile(r"^-?\d+$")
PAGE_MAP = {1: 1, 2: 2, 3: 3, 4: 4, 6: 6, 7: 7, 9: 8}     # PDF sahifa → ichki (Qashqadaryo jadvallari) raqami
GAP = 4.5


def _tokens(words: list[dict]) -> list[dict]:
    """Bir qatordagi so'zlarni kataklarga yig'adi: «172» «946» → 172946, «↑» «5» → ↑5."""
    out: list[dict] = []
    for w in sorted(words, key=lambda w: w["x0"]):
        t = w["text"]
        arrow = t[:1] in "↑↓"
        last = out[-1] if out else None
        if last and last["arrow_only"] and w["x0"] - last["x1"] < GAP + 3:
            last["text"] += t
            last["x1"] = w["x1"]
            last["arrow_only"] = False
            continue
        if last and not arrow and not last["pct"] and w["x0"] - last["x1"] < GAP \
                and (NUM.match(t) or t.endswith("%")):
            last["text"] += t
            last["x1"] = w["x1"]
            last["pct"] = t.endswith("%")
            continue
        out.append({"text": t, "x0": w["x0"], "x1": w["x1"], "arrow_only": t in ("↑", "↓"), "pct": t.endswith("%")})
    return out


def _is_delta(t: dict) -> bool:
    return t["text"][:1] in "↑↓"


def _rows(ws: list[dict], ytop: float, limit: int = 15) -> list[list[dict]]:
    body = [w for w in ws if (w["top"] + w["bottom"]) / 2 >= ytop - 3]
    body.sort(key=lambda w: (w["top"] + w["bottom"]) / 2)
    rows: list[list[dict]] = []
    last = None
    for w in body:
        yc = (w["top"] + w["bottom"]) / 2
        if last is None or yc - last > 5:
            rows.append([])
        rows[-1].append(w)
        last = yc
    return rows


def _split(row: list[dict]) -> tuple[str, list[dict]]:
    name = " ".join(w["text"] for w in sorted(row, key=lambda w: w["x0"]) if re.search(r"[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳ‘’ʻ]", w["text"]) and w["text"][:1] not in "↑↓")
    nums = [w for w in row if not (re.search(r"[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳ‘’ʻ]", w["text"]) and w["text"][:1] not in "↑↓")]
    return name.strip(), _tokens(nums)


def _cell(tok: dict | None, d: dict | None) -> dict:
    v = p = None
    if tok:
        t = tok["text"]
        if t.endswith("%"):
            p = t
        else:
            v = int(t) if NUM.match(t) else None
    dv = None
    if d:
        m = re.search(r"-?\d+", d["text"][1:])
        if m:
            dv = (1 if d["text"][0] == "↑" else -1) * abs(int(m.group()))
    return {"v": v, "p": p, "d": dv}


def _page_rows(ws: list[dict]) -> tuple[list[dict], list[dict]] | None:
    parsed: list = []
    for j in sorted([w for w in ws if w["text"] in R.JAMI and w["top"] > 200], key=lambda w: w["top"]):
        cand = [_split(r) for r in _rows(ws, (j["top"] + j["bottom"]) / 2)]
        cand = [(n, t) for n, t in cand if n and t]
        if cand and cand[0][0] in R.JAMI and len([t for t in cand[0][1] if not _is_delta(t)]) >= 3:
            parsed = cand
            break
    if not parsed:
        return None
    jt = [t for t in parsed[0][1] if not _is_delta(t)]
    if len(jt) < 3:
        return None
    anchors = [(t["x0"] + t["x1"]) / 2 for t in jt]

    def build(toks: list[dict]) -> list[dict]:
        cells: list[dict | None] = [None] * len(anchors)
        deltas: dict[int, dict] = {}
        for t in toks:
            if _is_delta(t):
                idx = max([i for i, a in enumerate(anchors) if a < t["x0"] + 1] or [0])
                deltas[idx] = t
            else:
                c = (t["x0"] + t["x1"]) / 2
                i = min(range(len(anchors)), key=lambda k: abs(anchors[k] - c))
                if cells[i] is None:
                    cells[i] = t
        return [_cell(cells[i], deltas.get(i)) for i in range(len(anchors))]

    jami = build(parsed[0][1])
    regions = []
    for n, toks in parsed[1:1 + 14]:
        if len([t for t in toks if not _is_delta(t)]) < 2:
            continue
        regions.append({"name": n, "cells": build(toks)})
    return jami, regions


def looks_like(data: bytes) -> bool:
    """PDF respublika (R-Dynamic) hisobotimi: jadvalda barcha viloyatlar (Qoraqalpoq …) bor."""
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            txt = " ".join(w["text"] for w in pdf.pages[0].extract_words(x_tolerance=1.2))
    except Exception:  # noqa: BLE001
        return False
    return "Qoraqalpoq" in txt and "Farg" in txt and "Xorazm" in txt


def parse_pdf(data: bytes) -> dict:
    """{"start","end","pages":[{"n" (ichki), "pdf", "title","cells","rows"}]} — faqat kerakli sahifalar."""
    pages, start, end = [], None, None
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for pn, pg in enumerate(pdf.pages, 1):
            if pn not in PAGE_MAP:                       # diagramma / SmartApp sahifalari o'qilmaydi (tezroq)
                continue
            ws = pg.extract_words(x_tolerance=1.2)
            if not ws:
                continue
            if pn == 1 and not any(w["text"].startswith("Qoraqalpoq") for w in ws):
                return {"start": None, "end": None, "pages": []}      # respublika PDF'i emas
            if not end:
                txt = " ".join(w["text"] for w in sorted(ws, key=lambda w: (round(w["top"]), w["x0"])))
                m = R.RANGE_RE.search(txt)
                if m:
                    start = R._d(m.group(1))
                    end = R._d(m.group(2)) if m.group(2) else None
                    if not end:
                        d2 = R.DATE_RE.findall(txt)
                        end = R._d(".".join(d2[0])) if d2 else None
            got = _page_rows(ws)
            if not got:
                continue
            jami, regions = got
            n = len(jami)
            pages.append({"n": PAGE_MAP[pn], "pdf": pn, "title": "",
                          "cells": [{"label": f"Ustun {i + 1}", **c} for i, c in enumerate(jami)],
                          "rows": [r for r in regions if len(r["cells"]) == n]})
    pages = [p for p in pages if len(p["rows"]) >= 10]
    return {"start": start, "end": end, "pages": pages}


def parse_report(data: bytes) -> dict:
    """parse_pdf + lotincha sarlavha va ustun nomlari (Qashqadaryo bilan bir xil)."""
    r = parse_pdf(data)
    out = []
    for p in r["pages"]:
        n = len(p["cells"])
        cells = [{"label": R.label_for(p["n"], i, n, r["end"], c["label"]), "v": c["v"], "p": c["p"], "d": c["d"]}
                 for i, c in enumerate(p["cells"])]
        out.append({"n": p["n"], "title": R.TITLES.get(p["n"], p["title"]), "cells": cells, "rows": p["rows"]})
    r["pages"] = out
    return r


def compare(a: dict | None, b: dict, base_iso: str, to_iso: str) -> list[dict]:
    """Qashqadaryo bilan bir xil solishtirish + har sahifaga ustun nomlari (saralash/reyting uchun)."""
    res = R.compare(a, b, base_iso, to_iso)
    pages = {p["n"]: p for p in b["pages"]}
    for x in res:
        p = pages.get(x["n"])
        x["labels"] = [c.get("label", "") for c in p["cells"]] if p else []
    return res
