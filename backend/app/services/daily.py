"""Kunlik topshiriq bo'limi: 5 ta Excel fayldan jadvallar va xodimlar bo'yicha topshiriq faylini tayyorlash.

Boshqa bo'limlardan to'liq ajratilgan: o'z jadvali (daily_batches), o'z papkasi (data/daily), o'z sozlamalari (daily_settings).

Fayllar:  area (AreaInformationReport) · status (CommissioningStatus) · direct (DirectMeter)
          nometer (NoMeterData) · online (Online_Device_Monitoring_Report — faqat offline qurilmalar)

Ustun nomlari dastur tiliga bog'liq bo'lishi mumkin, shuning uchun hamma narsa katak o'rni va qator ko'rinishi
bo'yicha aniqlanadi — sarlavha matniga tayanilmaydi."""
import json
import re
from collections import defaultdict
from functools import lru_cache
from datetime import date, datetime
from io import BytesIO

import openpyxl
import xlsxwriter
from sqlalchemy import text

from ..config import settings as app_settings
from ..db import engine
from . import filenames as FN

KINDS = ["area", "status", "direct", "nometer", "online"]
LABEL = {"area": "AreaInformationReport", "status": "CommissioningStatus", "direct": "DirectMeter",
         "nometer": "NoMeterData", "online": "Online_Device_Monitoring"}
MAX_XLSX_MB = 120

_TAG = re.compile(r"<[^>]*>")


def _n(v) -> str:
    """Sarlavhani solishtirish uchun: kichik harf, HTML teglarsiz, ortiqcha bo'shliqsiz."""
    return re.sub(r"\s+", " ", _TAG.sub(" ", str(v or ""))).strip().lower().rstrip(":")


# Ustunlar faqat KATAK O'RNI bo'yicha olinadi (sarlavha matni dastur tiliga qarab o'zgarishi mumkin, shuning uchun
# hech qayerda sarlavha nomiga tayanilmaydi). Fayl turi ham ma'lumot qatorining ko'rinishidan aniqlanadi.
POS = {
    "area": {"esp": 4, "ss": 6, "fd": 8, "trc": 9, "tr": 10, "mgr": 12},
    "status": {"esp": 1, "tr": 2, "dcu": 3, "pcs": 7, "poll": 10},
    "direct": {"esp": 1, "ss": 3, "fd": 4, "tr": 5, "meter": 6, "acc": 7, "ctype": 8, "name": 9, "addr": 10, "mtype": 11, "gps": 12},
    "nometer": {"esp": 1, "ss": 2, "fd": 3, "tr": 4, "acc": 5, "ctype": 6, "name": 7, "meter": 8, "link": 9, "mgr": 10,
                "days": 12, "time": 13, "gps": 14, "addr": 15},
    "online": {"esp": 0, "ss": 1, "fd": 2, "tr": 3, "dev": 5, "st": 6, "time": 7, "lat": 9, "lon": 10, "mgr": 15},
}
FILE_HINT = {"area": ("areainformation", "area_information"), "status": ("commissioning",),
             "direct": ("directmeter", "direct_meter"), "nometer": ("nometer", "no_meter"),
             "online": ("online_device", "onlinedevice")}
_DIG = re.compile(r"^\d+$")
_TIME = re.compile(r"^\d{1,4}:\d{2}")


class DailyError(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato."""


def _s(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"\s+", " ", str(v)).strip()


def _num(v) -> float | None:
    try:
        return float(str(v).replace(",", ".").replace(" ", "")) if str(v or "").strip() else None
    except ValueError:
        return None


def _c(r, i: int) -> str:
    return _s(r[i]) if i < len(r) else ""


def _is_data(kind: str, r) -> bool:
    """Qator shu turdagi fayl ma'lumot qatorimi? Sarlavha, sarlavhadan oldingi qatorlar va «Jami» qatorlari o'tmaydi."""
    n = len(r)
    if kind == "area":
        return n >= 13 and bool(_c(r, 4)) and all(_DIG.match(_c(r, i)) for i in (1, 3, 5, 7, 9))
    if kind == "status":
        return (11 <= n <= 12 and _num(_c(r, 0)) is not None and bool(_c(r, 1)) and _num(_c(r, 1)) is None
                and bool(_c(r, 2)) and _num(_c(r, 7)) is not None and (_num(_c(r, 10)) is not None or not _c(r, 10)))
    if kind == "direct":
        return (13 <= n <= 14 and _num(_c(r, 0)) is not None and bool(_c(r, 1)) and _DIG.match(_c(r, 2)) is not None
                and bool(_c(r, 6)) and bool(_c(r, 7)))
    if kind == "nometer":
        return (n >= 15 and _num(_c(r, 0)) is not None and bool(_c(r, 1)) and _num(_c(r, 12)) is not None
                and _TIME.match(_c(r, 13)) is not None)
    if kind == "online":
        return n >= 16 and bool(_c(r, 0)) and bool(_c(r, 5)) and _dt(_c(r, 7)) is not None
    return False


def _peek(src, limit: int = 15) -> list[tuple]:
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        ws.reset_dimensions()      # ba'zi eksportlarda o'lcham noto'g'ri yoziladi (1x1)
        return [tuple(r) for _i, r in zip(range(limit), ws.iter_rows(values_only=True))]
    finally:
        wb.close()


def detect(src, filename: str = "") -> tuple[str, int]:
    """Fayl turini ma'lumot qatorlarining ko'rinishiga qarab aniqlaydi (sarlavha matniga qaramaydi) → (tur, 0)."""
    try:
        rows = _peek(src)
    except Exception as e:  # noqa: BLE001
        raise DailyError(f"«{filename}» — Excel (.xlsx) faylni o'qib bo'lmadi") from e
    fname = re.sub(r"[^a-z0-9_]", "", (filename or "").lower())
    best, best_kind = 0.0, None
    for kind in KINDS:
        score = float(sum(_is_data(kind, r) for r in rows))
        if score and any(h in fname for h in FILE_HINT[kind]):
            score += 0.5            # faqat teng holatda yordam beradi
        if score > best:
            best, best_kind = score, kind
    if not best_kind:
        raise DailyError(f"«{filename}» — fayl turi aniqlanmadi: ustunlar tartibi 5 ta kutilgan fayldan birortasiga mos kelmadi")
    return best_kind, 0


def read(src, kind: str, hrow: int | None = None) -> list[dict]:
    """Faylni o'qiydi: faqat ma'lumot qatorlari, ustunlar katak o'rni bo'yicha → [{kalit: matn}]."""
    pos = POS[kind]
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        ws.reset_dimensions()
        out = [{k: _c(r, j) for k, j in pos.items()} for r in ws.iter_rows(values_only=True) if r and _is_data(kind, r)]
    finally:
        wb.close()
    if not out:
        raise DailyError(f"{LABEL[kind]}: ma'lumot qatorlari topilmadi (ustunlar tartibi kutilganidan farq qiladi)")
    return out


# ----------------------------------------------------------------------------------------- sozlamalar
ESP_ORDER = ["Baxoriston ETK", "G‘uzor TETK", "Dehqonobod TETK", "Qamashi TETK", "Qarshi ShETK", "Qarshi TETK",
             "Koson TETK", "Kasbi TETK", "Kitob TETK", "Mirishkor TETK", "Muborak TETK", "Nishon TETK",
             "Chiroqchi TETK", "Shahrisabz ShETK", "Shahrisabz TETK", "Yakkabog‘ TETK", "Ko‘kdala TETK"]
FILE_KEYS = [("t1", "fn_t1", "t1_title"), ("t2", "fn_t2", "t2_title"), ("task", "fn_task", "task_title")]
PLACEHOLDERS = {"nom": "jadval nomi", "hudud": "hudud nomi", "sana": "sana, 2026-11-23", "sana_dmy": "sana, 23.11.2026",
                "yil": "yil", "oy": "oy raqami", "kun": "kun raqami"}
for _k in ("daily_t1", "daily_t2", "daily_task"):
    FN.ALLOWED[_k] = set(PLACEHOLDERS)
DEFAULTS = {
    "region": "Qashqadaryo",
    "t1_title": "Konsentratorlar",
    "t2_title": "Aloqadan chiqib ketgan hisoblagichlar soni",
    "task_title": "Kunlik topshiriq",
    "offline_days": 3,
    "time_edges": [2, 7, 30, 90],
    "esp_order": ESP_ORDER,
    "types": {},
    "fn_t1": "{nom}_{sana_dmy}",
    "fn_t2": "{nom}_{sana_dmy}",
    "fn_task": "{nom}_{sana_dmy}",
    "chats": {"t1": [], "t2": [], "task": []},
}


def load_settings() -> dict:
    with engine.connect() as c:
        raw = c.execute(text("SELECT v FROM daily_settings WHERE k='main'")).scalar()
    try:
        cur = json.loads(raw) if raw else {}
    except ValueError:
        cur = {}
    out = {**DEFAULTS, **{k: v for k, v in cur.items() if k in DEFAULTS}}
    out["chats"] = {**DEFAULTS["chats"], **(cur.get("chats") or {})}
    return out


def save_settings(s: dict) -> None:
    from sqlalchemy.dialects.mysql import insert
    from ..models import DailySetting
    st = insert(DailySetting).values(k="main", v=json.dumps({k: s[k] for k in DEFAULTS}, ensure_ascii=False))
    with engine.begin() as c:
        c.execute(st.on_duplicate_key_update(v=st.inserted.v))


def validate_settings(s: dict) -> str | None:
    for k in ("region", "t1_title", "t2_title", "task_title"):
        if not str(s.get(k, "")).strip() or len(str(s[k])) > 120:
            return f"«{k}» bo'sh bo'lmasin (120 belgigacha)"
    if not isinstance(s.get("offline_days"), int) or not 1 <= s["offline_days"] <= 60:
        return "Offline kunlar 1 dan 60 gacha butun son bo'lsin"
    e = s.get("time_edges")
    if not (isinstance(e, list) and 2 <= len(e) <= 8 and all(isinstance(x, int) and x >= 0 for x in e)
            and all(a < b for a, b in zip(e, e[1:]))):
        return "Kun oraliqlari o'sib boruvchi butun sonlar bo'lsin (masalan: 2, 7, 30, 90)"
    for fk, tk in ((f"fn_{k}", k) for k, _f, _t in FILE_KEYS):
        err = FN.validate("daily_" + tk, s.get(fk, ""))
        if err:
            return f"Fayl nomi ({tk}): {err}"
    if s.get("types") and not all(v in CATS for v in s["types"].values()):
        return "Iste'molchi turi noto'g'ri"
    return None


def out_specs(s: dict) -> list[dict]:
    """Yuboriladigan/yuklab olinadigan natija fayllari (tartib = Telegramga yuborish tartibi).
    group — qaysi kanal/guruh ro'yxatidan standart tanlanadi; default — yuborish oynasida oldindan belgilanadimi."""
    n, lab = s["offline_days"], day_labels(s["time_edges"])
    sp = [
        {"k": "img1", "ext": "png", "title": s["t1_title"], "tpl": "fn_t1", "group": "t1", "default": True},
        {"k": "img2", "ext": "png", "title": s["t2_title"], "tpl": "fn_t2", "group": "t2", "default": True},
        {"k": "off", "ext": "xlsx", "title": f"Offline konsentratorlar ({n} kundan ortiq)", "tpl": "fn_task", "group": "task", "default": True},
        {"k": "low", "ext": "xlsx", "title": "Obxod olish darajasi past konsentratorlar (0-50%)", "tpl": "fn_task", "group": "task", "default": True},
        {"k": "prim", "ext": "xlsx", "title": "To'g'ridan to'g'ri ulanish (Primichka)", "tpl": "fn_task", "group": "task", "default": True},
    ]
    sp += [{"k": f"nm{i}", "ext": "xlsx", "title": f"Aloqadan chiqib ketgan hisoblagichlar {l}", "tpl": "fn_task", "group": "task",
            "default": True} for i, l in enumerate(lab)]
    sp += [{"k": "t1", "ext": "xlsx", "title": s["t1_title"], "tpl": "fn_t1", "group": "t1", "default": False},
           {"k": "t2", "ext": "xlsx", "title": s["t2_title"], "tpl": "fn_t2", "group": "t2", "default": False},
           {"k": "task", "ext": "xlsx", "title": s["task_title"], "tpl": "fn_task", "group": "task", "default": False}]
    return sp


def spec_of(s: dict, which: str) -> dict | None:
    return next((x for x in out_specs(s) if x["k"] == which), None)


def file_name(s: dict, which: str, end) -> str:
    sp = spec_of(s, which)
    ctx = FN.context(end, None, hudud=s["region"], nom=sp["title"])
    return FN.render(s[sp["tpl"]], ctx, sp["ext"], sp["title"].replace(" ", "_") or "Hisobot")


def names_example(s: dict) -> dict:
    return {x["k"]: file_name(s, x["k"], "2026-11-23") for x in out_specs(s)}


# ----------------------------------------------------------------------------------------- hisoblash
CATS = ("aholi", "ulgurji", "balans")
_GUESS = [("aholi", ("быт", "населен", "resid", "household", "domestic", "aholi", "maishiy")),
          ("ulgurji", ("промыш", "юр", "industr", "commerc", "ulgurji", "корпор", "бюджет")),
          ("balans", ("баланс", "индикатор", "balance", "indicator", "balans"))]


def categorize(raw: str, mapping: dict) -> str | None:
    key = _n(raw)
    saved = {_n(k): v for k, v in (mapping or {}).items()}
    if key in saved:
        return saved[key]
    for cat, words in _GUESS:
        if any(w in key for w in words):
            return cat
    return None


def _dt(v) -> datetime | None:
    s = _s(v)
    for f in ("%d/%m/%Y %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    return None


def _gps(s: str) -> tuple[float, float] | None:
    m = re.findall(r"-?\d+(?:[.,]\d+)?", s or "")
    if len(m) < 2:
        return None
    a, b = float(m[0].replace(",", ".")), float(m[1].replace(",", "."))
    return (a, b) if abs(a) > 0.001 and abs(b) > 0.001 and abs(a) <= 90 and abs(b) <= 180 else None


def day_labels(e: list[int]) -> list[str]:
    """Fayl nomlari uchun: har doim kun bilan (2-7 kun … 90 kundan ortiq)."""
    return [f"{a}-{b} kun" for a, b in zip(e, e[1:])] + [f"{e[-1]} kundan ortiq"]


def edge_labels(e: list[int]) -> list[str]:
    out = []
    for a, b in zip(e, e[1:]):
        out.append(f"{a // 30}-{b // 30} oy" if b > 30 and a % 30 == 0 and b % 30 == 0 else f"{a}-{b} kun")
    last = e[-1]
    out.append(f"{last // 30} oydan ortiq" if last >= 30 and last % 30 == 0 else f"{last} kundan ortiq")
    return out


def _esp_list(order: list[str], *groups) -> list[str]:
    seen = set(order)
    extra = sorted({r["esp"] for g in groups for r in g} - seen)
    return list(order) + extra


def _nat(s: str):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s or "")]


def unknown_types(nometer: list[dict], mapping: dict) -> list[dict]:
    cnt = defaultdict(int)
    for r in nometer:
        if categorize(r["ctype"], mapping) is None:
            cnt[r["ctype"]] += 1
    return [{"value": k, "count": v} for k, v in sorted(cnt.items(), key=lambda x: -x[1])]


def compute(end: date, data: dict, s: dict) -> dict:
    """Ikki jadval qiymatlari (hudud kesimida). data: {tur: [qatorlar]}."""
    esps = _esp_list(s["esp_order"], *[data[k] for k in KINDS])
    A = {e: defaultdict(int) for e in esps}
    seen = set()
    for r in data["area"]:
        k = (r["esp"], r["ss"], r["fd"], r["tr"])
        if k not in seen:
            seen.add(k)
            A[r["esp"]]["tp"] += 1
    for r in data["status"]:
        if not r["dcu"] or r["dcu"].lower() in ("none", "null", "-"):
            continue
        a = A[r["esp"]]
        a["cas"] += 1
        pcs, poll = _num(r["pcs"]) or 0, _num(r["poll"]) or 0
        if pcs <= 0:
            a["un"] += 1
        elif poll <= 0:
            a["p0"] += 1
        elif poll <= 50:
            a["p1"] += 1
        elif poll <= 80:
            a["p2"] += 1
        else:
            a["p3"] += 1
    n = s["offline_days"]
    for r in data["online"]:
        if _n(r.get("st")) in ("online", "онлайн"):
            continue
        a = A[r["esp"]]
        a["off"] += 1
        t = _dt(r["time"])
        if t is None or (end - t.date()).days >= n:     # bugun va undan oldingi n-1 kun (21, 22, 23.11) chiqariladi
            a["offgt"] += 1
    for e in esps:
        A[e]["online"] = max(A[e]["cas"] - A[e]["off"], 0)
    E = s["time_edges"]
    for r in data["nometer"]:
        a = A[r["esp"]]
        a["tot"] += 1
        c = categorize(r["ctype"], s["types"])
        if c:
            a[{"aholi": "aho", "ulgurji": "ulg", "balans": "bal"}[c]] += 1
        d = _num(r["days"])
        if d is not None:
            for i in range(len(E)):
                if d >= E[i] and (i == len(E) - 1 or d < E[i + 1]):
                    a[f"k{i}"] += 1
                    break
    for r in data["direct"]:
        A[r["esp"]]["dir"] += 1
    lab = edge_labels(E)
    t1_keys = ["tp", "cas", "online", "off", "offgt", "p0", "p1", "p2", "p3", "un"]
    t2_keys = ["tot", "aho", "ulg", "bal"] + [f"k{i}" for i in range(len(lab))] + ["dir"]
    return {"date": end.isoformat(), "region": s["region"], "offline_days": n,
            "tables": [_table_t1(s, esps, A, t1_keys), _table_t2(s, esps, A, t2_keys, lab)]}


def _rows(esps, A, keys):
    rows = [{"name": e, "v": {k: A[e][k] for k in keys}} for e in esps]
    return rows, {k: sum(r["v"][k] for r in rows) for k in keys}


def _table_t1(s, esps, A, keys) -> dict:
    n = s["offline_days"]
    H = lambda l, rs=1, cs=1, c="", **kw: {"l": l, "rs": rs, "cs": cs, "c": c, **kw}      # noqa: E731
    head = [
        [H("Hudud nomi", 4, 1, "name"), H("Dasturda mavjud transformatorlar soni", 4, 1, rot=True), H(s["t1_title"], 1, 9, "title")],
        [H("CAS ga yuklangan", 3, 1, rot=True), H("shundan", 1, 3, it=True), H("Obxod olish darajasi bo'yicha soni", 1, 5)],
        [H("Online", 2, 1, "green"), H("Offline (jami)", 2, 1, "red"), H(f"shundan {n} kundan ortiq", 2, 1, "red", rot=True),
         H("0%"), H("1-50%"), H("50-80%"), H("80-100%"), H("Istemolchi biriktirilmagan")],
        [H("soni", c="red") for _ in range(5)],
    ]
    cols = [{"k": "tp"}, {"k": "cas"}, {"k": "online", "c": "green"}, {"k": "off", "c": "red", "cream": True},
            {"k": "offgt", "c": "red", "cream": True}, {"k": "p0", "c": "red", "cream": True}, {"k": "p1", "c": "red", "cream": True},
            {"k": "p2", "c": "red", "cream": True}, {"k": "p3"}, {"k": "un", "c": "red", "cream": True}]
    rows, total = _rows(esps, A, keys)
    return {"key": "t1", "title": s["t1_title"], "head": head, "cols": cols, "rows": rows, "total": total}


def _table_t2(s, esps, A, keys, lab) -> dict:
    H = lambda l, rs=1, cs=1, c="", **kw: {"l": l, "rs": rs, "cs": cs, "c": c, **kw}      # noqa: E731
    k = len(lab)
    head = [
        [H("Hudud nomi", 4, 1, "name"), H(s["t2_title"], 1, 3 + k + 1 + 1, "title red")],
        [H("Jami", 1, 1, "sub"), H("Iste'molchi turi kesimida", 1, 3, "sub"), H("Vaqtlar kesimida", 1, k, "sub"),
         H("To'g'ridan to'g'ri ulanish (Primichka)", 3, 1, "red")],
        [H("soni", 2, 1, "red"), H("Aholi", 1, 1, "green"), H("Ulgurji", 1, 1, "blue"), H("Balans", 1, 1, "amber")]
        + [H(x) for x in lab],
        [H("soni", c="red") for _ in range(3 + k)],
    ]
    cols = ([{"k": "tot", "c": "red", "cream": True}, {"k": "aho"}, {"k": "ulg"}, {"k": "bal"}]
            + [{"k": f"k{i}"} for i in range(k)] + [{"k": "dir"}])
    rows, total = _rows(esps, A, keys)
    return {"key": "t2", "title": s["t2_title"], "head": head, "cols": cols, "rows": rows, "total": total}


# ----------------------------------------------------------------------------------------- Excel: jadvallar
_COL = {"green": "#00B050", "red": "#C00000", "blue": "#4472C4", "amber": "#C55A11", "": "#000000", "sub": "#000000",
        "name": "#000000", "title": "#000000", "title red": "#C00000"}
LINE = "#2B2F36"


def table_xlsx(tb: dict, region: str, end: date) -> bytes:
    bio = BytesIO()
    wb = xlsxwriter.Workbook(bio, {"in_memory": True})
    ws = wb.add_worksheet(tb["title"][:31])
    F = lambda **kw: wb.add_format({"font_name": "Calibri", "font_size": 11, "border": 1, "border_color": LINE,  # noqa: E731
                                    "align": "center", "valign": "vcenter", **kw})
    ncols = 1 + len(tb["cols"])
    ws.set_column(0, 0, 22)
    ws.set_column(1, ncols - 1, 13)
    ws.set_row(0, 22)
    ws.write(0, 0, "Hudud nomi:", wb.add_format({"font_name": "Calibri", "font_size": 13, "align": "right", "valign": "vcenter"}))
    ws.merge_range(0, 1, 0, 2, region, wb.add_format({"font_name": "Calibri", "font_size": 13, "bold": True,
                                                       "font_color": "#0066FF", "align": "left", "valign": "vcenter"}))
    ws.write(0, ncols - 1, f"{end:%d.%m.%Y}", wb.add_format({"font_name": "Calibri", "font_size": 12, "bold": True,
                                                              "align": "right", "valign": "vcenter"}))
    hdr_rows = len(tb["head"])
    occupied = set()
    for ri, row in enumerate(tb["head"]):
        ci = 0
        for h in row:
            while (ri, ci) in occupied:
                ci += 1
            color = "title red" if h["c"] == "title red" else h["c"].split()[-1] if h["c"] else ""
            fmt = F(bold=True, bg_color="#DDEBF7", text_wrap=True, font_color=_COL.get(color, "#000000"),
                    italic=bool(h.get("it")), rotation=90 if h.get("rot") else 0,
                    font_size=16 if h["c"] == "name" else 12 if h["c"] in ("title", "title red") else 11)
            for dr in range(h["rs"]):
                for dc in range(h["cs"]):
                    occupied.add((ri + dr, ci + dc))
            if h["rs"] > 1 or h["cs"] > 1:
                ws.merge_range(1 + ri, ci, 1 + ri + h["rs"] - 1, ci + h["cs"] - 1, h["l"], fmt)
            else:
                ws.write(1 + ri, ci, h["l"], fmt)
            ci += h["cs"]
    for r, hh in enumerate([24, 22, 70, 18]):
        ws.set_row(1 + r, hh)
    r0 = 1 + hdr_rows

    def line(r, name, vals, total=False):
        base = {"bold": True, "num_format": "#,##0"}
        nm = F(bold=total, bg_color="#FFE699" if total else "#FFFFFF", font_size=12 if total else 11,
               **({} if total else {"align": "left"}))
        ws.write(r, 0, name, nm)
        for i, c in enumerate(tb["cols"]):
            bg = "#FFE699" if total else "#FFFDEF" if c.get("cream") else "#FFFFFF"
            f = F(**base, bg_color=bg, font_color=_COL[c.get("c", "")], align="right")
            v = vals.get(c["k"], 0)
            if v:
                ws.write_number(r, 1 + i, v, f)
            else:
                ws.write_blank(r, 1 + i, None, f)
        ws.set_row(r, 20)

    line(r0, "Jami", tb["total"], True)
    for i, row in enumerate(tb["rows"]):
        line(r0 + 1 + i, row["name"], row["v"])
    ws.freeze_panes(r0 + 1, 1)
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    wb.close()
    return bio.getvalue()


# ----------------------------------------------------------------------------------------- Excel: nomma-nom ro'yxatlar
SHEETS = [
    ("Offline kontsentratorlar", "offline", ["Qurilma raqami", "Offline vaqti", "Offline (kun)"]),
    ("Aloqasiz hisoblagichlar", "nometer", ["Hisob raqami", "Iste'molchi", "Iste'molchi turi", "Hisoblagich raqami",
                                            "Aloqa turi", "Aloqasiz (kun)", "Manzil"]),
    ("Primichka", "direct", ["Hisob raqami", "Iste'molchi", "Iste'molchi turi", "Hisoblagich raqami", "Hisoblagich turi", "Manzil"]),
]
EXTRA = {"offline": SHEETS[0][2], "nometer": SHEETS[1][2], "direct": SHEETS[2][2],
         "low": ["Konsentrator raqami", "O'rnatilgan (dona)", "Obxod (%)"]}
WIDTHS = {"offline": [18, 20, 12], "nometer": [14, 30, 16, 16, 10, 12, 40], "direct": [14, 30, 16, 16, 18, 40],
          "low": [18, 14, 12]}


def _norm_tr(x: str) -> str:
    return (x or "").strip().lstrip("0")


def _task_rows(end: date, data: dict, order: list[str]) -> dict[str, list[dict]]:
    mgr = {}
    for r in data["area"]:
        mgr.setdefault((r["esp"], r["ss"], r["fd"], r["tr"]), r["mgr"])
    rank = {e: i for i, e in enumerate(order)}

    def base(r):
        return {"esp": r["esp"], "ss": r["ss"], "fd": r["fd"], "tr": r["tr"],
                "mgr": mgr.get((r["esp"], r["ss"], r["fd"], r["tr"])) or r.get("mgr", "")}

    out = {"offline": [], "nometer": [], "direct": [], "low": []}
    seen = set()
    for r in data["online"]:
        if _n(r.get("st")) in ("online", "онлайн") or ("o", r["dev"]) in seen:
            continue
        seen.add(("o", r["dev"]))
        t = _dt(r["time"])
        loc = (_num(r["lat"]), _num(r["lon"]))
        d = (end - t.date()).days if t else None
        out["offline"].append({**base(r), "loc": loc if all(loc) else None, "d": d,
                               "x": [r["dev"], t.strftime("%d.%m.%Y %H:%M:%S") if t else r["time"], "" if d is None else d]})
    for r in data["nometer"]:
        k = ("n", r["meter"] or r["acc"])
        if k in seen and r["meter"]:
            continue
        seen.add(k)
        d = _num(r["days"])
        out["nometer"].append({**base(r), "loc": _gps(r["gps"]), "d": d,
                               "x": [r["acc"], r["name"], r["ctype"], r["meter"], r["link"],
                                     int(d) if d is not None else "", r["addr"]]})
    for r in data["direct"]:
        k = ("d", r["meter"] or r["acc"])
        if k in seen and r["meter"]:
            continue
        seen.add(k)
        out["direct"].append({**base(r), "loc": _gps(r["gps"]), "d": None,
                              "x": [r["acc"], r["name"], r["ctype"], r["meter"], r["mtype"], r["addr"]]})
    # obxod olish darajasi past (0–50%) konsentratorlar: podstansiya/fider/xodim «Area» faylidan TP raqami bo'yicha olinadi
    area = {}
    for r in data["area"]:
        for t in (r["tr"], r["trc"]):
            area.setdefault((r["esp"], _norm_tr(t)), r)
    dev_loc = {r["dev"]: (_num(r["lat"]), _num(r["lon"])) for r in data["online"] if _num(r["lat"]) and _num(r["lon"])}
    tp_loc = {}
    for r in (*data["nometer"], *data["direct"]):
        g = _gps(r["gps"])
        if g:
            tp_loc.setdefault((r["esp"], _norm_tr(r["tr"])), g)
    low_seen = set()
    for r in data["status"]:
        dcu = r["dcu"]
        if not dcu or dcu.lower() in ("none", "null", "-") or dcu in low_seen:
            continue
        pcs, poll = _num(r["pcs"]) or 0, _num(r["poll"]) or 0
        if pcs <= 0 or poll > 50:
            continue
        low_seen.add(dcu)
        a = area.get((r["esp"], _norm_tr(r["tr"])))
        loc = dev_loc.get(dcu) or tp_loc.get((r["esp"], _norm_tr(r["tr"])))
        out["low"].append({"esp": r["esp"], "ss": a["ss"] if a else "", "fd": a["fd"] if a else "",
                           "tr": a["tr"] if a else r["tr"], "mgr": a["mgr"] if a else "", "loc": loc, "d": None,
                           "x": [dcu, int(pcs), int(poll) if float(poll).is_integer() else round(poll, 1)]})
    for rows in out.values():      # xodim bo'yicha: bo'sh xodimlar oxirida
        rows.sort(key=lambda x: (not x["mgr"], x["mgr"].lower(), rank.get(x["esp"], 999), _nat(x["ss"]), _nat(x["fd"]), _nat(x["tr"])))
    return out


def _formats(wb):
    F = lambda **kw: wb.add_format({"font_name": "Calibri", "font_size": 11, "border": 1, "border_color": LINE, "valign": "vcenter", **kw})  # noqa: E731
    return (F(bold=True, bg_color="#DDEBF7", align="center", text_wrap=True), F(), F(font_color="#0563C1", underline=1),
            wb.add_format({"font_name": "Calibri", "font_size": 13, "bold": True}))


def _write_sheet(wb, fm, name: str, heading: str, extra: list[str], widths: list[int], data_rows: list[dict]) -> None:
    head, cell, link, ttl = fm
    ws = wb.add_worksheet(name[:31])
    cols = ["#", "Tuman", "Podstansiya", "Fider", "TP raqami", *extra, "Joylashuv", "Xodim(lar)"]
    ws.write(0, 0, f"{heading} ({len(data_rows)} ta)", ttl)
    for j, c in enumerate(cols):
        ws.write(1, j, c, head)
    for j, w in enumerate([6, 18, 26, 20, 10] + widths + [22, 48]):
        ws.set_column(j, j, w)
    lc = 5 + len(extra)
    for i, r in enumerate(data_rows):
        rr = 2 + i
        ws.write_number(rr, 0, i + 1, cell)
        for j, v in enumerate([r["esp"], r["ss"], r["fd"], r["tr"], *r["x"]], 1):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                ws.write_number(rr, j, v, cell)
            else:
                ws.write_string(rr, j, v or "", cell)
        if r["loc"]:
            la, lo = r["loc"]
            ws.write_url(rr, lc, f"https://www.google.com/maps?q={la:.6f},{lo:.6f}", link, f"{la:.6f}, {lo:.6f}")
        else:
            ws.write_blank(rr, lc, None, cell)
        ws.write_string(rr, lc + 1, r["mgr"] or "", cell)
    ws.freeze_panes(2, 5)
    ws.autofilter(1, 0, 1 + max(len(data_rows), 1), len(cols) - 1)
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.repeat_rows(1)


def _book(build) -> bytes:
    bio = BytesIO()
    wb = xlsxwriter.Workbook(bio, {"in_memory": True, "strings_to_urls": False, "strings_to_numbers": False})
    build(wb, _formats(wb))
    wb.close()
    return bio.getvalue()


def task_xlsx(end: date, data: dict, s: dict) -> tuple[bytes, dict]:
    """Eski umumiy fayl: 3 varaqli (offline / aloqasiz / primichka) — yuklab olish uchun qoldirilgan."""
    rows = _task_rows(end, data, s["esp_order"])

    def build(wb, fm):
        for name, key, extra in SHEETS:
            _write_sheet(wb, fm, name, f"{s['task_title']} — {end:%d.%m.%Y} — {name}", extra, WIDTHS[key], rows[key])
    return _book(build), {k: len(rows[k]) for k in ("offline", "nometer", "direct")}


def list_files(end: date, data: dict, s: dict) -> tuple[dict[str, bytes], dict[str, int]]:
    """7 ta alohida nomma-nom Excel: offline (N kundan ortiq), obxod past, primichka va aloqasiz hisoblagichlar kun oraliqlari bo'yicha."""
    rows = _task_rows(end, data, s["esp_order"])
    n, E = s["offline_days"], s["time_edges"]
    sets = {"off": ("offline", [r for r in rows["offline"] if r["d"] is None or r["d"] >= n]),
            "low": ("low", rows["low"]), "prim": ("direct", rows["direct"])}
    for i in range(len(E)):
        hi = E[i + 1] if i + 1 < len(E) else None
        sets[f"nm{i}"] = ("nometer", [r for r in rows["nometer"]
                                      if r["d"] is not None and r["d"] >= E[i] and (hi is None or r["d"] < hi)])
    files, counts = {}, {}
    titles = {x["k"]: x["title"] for x in out_specs(s)}
    for k, (kind, rs) in sets.items():
        counts[k] = len(rs)
        files[k] = _book(lambda wb, fm, k=k, kind=kind, rs=rs: _write_sheet(
            wb, fm, titles[k], f"{titles[k]} — {end:%d.%m.%Y}", EXTRA[kind], WIDTHS[kind], rs))
    return files, counts


# ----------------------------------------------------------------------------------------- jadvallar → rasm (Telegram uchun)
@lru_cache(maxsize=64)
def _font(size: int, bold: bool = False, italic: bool = False):
    from PIL import ImageFont
    from ..config import BASE
    name = "Carlito-" + ("BoldItalic" if bold and italic else "Bold" if bold else "Italic" if italic else "Regular") + ".ttf"
    return ImageFont.truetype(str(BASE / "assets" / "fonts" / name), size)


def _wrap(text: str, font, width: float) -> list[str]:
    lines, cur = [], ""
    for w in str(text).split():
        t = f"{cur} {w}".strip()
        if cur and font.getlength(t) > width:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + ([cur] if cur else [])


def table_png(tb: dict, region: str, end: date) -> bytes:
    """Jadvalni skrinshotdagi dizaynda rasm qilib chizadi (Excel faylidagi bilan bir xil ranglar va tartib)."""
    from PIL import Image, ImageDraw
    S = 1.7
    px = lambda v: int(round(v * S))      # noqa: E731
    NAME_W, COL_W, TOP_H, ROW_H, PAD = 215, 86, 36, 26, 10
    HEAD_H = [32, 30, 112, 26]
    ncols = len(tb["cols"])
    W = NAME_W + ncols * COL_W
    H = TOP_H + sum(HEAD_H) + (1 + len(tb["rows"])) * ROW_H
    img = Image.new("RGB", (px(W + 2 * PAD), px(H + 2 * PAD)), "white")
    d = ImageDraw.Draw(img)
    X = lambda ci: PAD + (0 if ci == 0 else NAME_W + (ci - 1) * COL_W)         # noqa: E731
    hy = [PAD + TOP_H]
    for h in HEAD_H:
        hy.append(hy[-1] + h)

    def rect(x, y, w, h, bg):
        d.rectangle([px(x), px(y), px(x + w), px(y + h)], fill=bg, outline=LINE, width=max(1, px(0.6)))

    def label(x, y, w, h, text, color="#000000", size=12, bold=False, italic=False, rot=False, align="center", pad=5):
        f = _font(px(size), bold, italic)
        if rot:
            lines = _wrap(text, f, px(h - 2 * pad))
            lay = Image.new("RGBA", (px(h), px(w)), (0, 0, 0, 0))
            ld, lh = ImageDraw.Draw(lay), px(size * 1.25)
            y0 = (px(w) - lh * len(lines)) / 2
            for i, ln in enumerate(lines):
                ld.text(((px(h) - f.getlength(ln)) / 2, y0 + i * lh), ln, font=f, fill=color)
            img.paste(lay.rotate(90, expand=True), (px(x), px(y)), lay.rotate(90, expand=True))
            return
        lines = _wrap(text, f, px(w - 2 * pad)) or [""]
        lh = px(size * 1.25)
        y0 = px(y) + (px(h) - lh * len(lines)) / 2
        for i, ln in enumerate(lines):
            tw = f.getlength(ln)
            xx = px(x) + (px(w) - tw) / 2 if align == "center" else px(x + pad) if align == "left" else px(x + w - pad) - tw
            d.text((xx, y0 + i * lh), ln, font=f, fill=color)

    # yuqori qator: hudud va sana
    label(PAD, PAD, NAME_W, TOP_H, "Hudud nomi:", size=14, align="right")
    label(PAD + NAME_W + 8, PAD, 4 * COL_W, TOP_H, region, "#0066FF", 14, True, align="left", pad=0)
    label(PAD + W - 3 * COL_W, PAD, 3 * COL_W, TOP_H, f"{end:%d.%m.%Y}", size=13, bold=True, align="right")
    # sarlavha
    occupied = set()
    for ri, row in enumerate(tb["head"]):
        ci = 0
        for h in row:
            while (ri, ci) in occupied:
                ci += 1
            for dr in range(h["rs"]):
                for dc in range(h["cs"]):
                    occupied.add((ri + dr, ci + dc))
            x = X(ci)
            w = NAME_W if ci == 0 else h["cs"] * COL_W
            y, hh = hy[ri], sum(HEAD_H[ri:ri + h["rs"]])
            rect(x, y, w, hh, "#DDEBF7")
            color = "title red" if h["c"] == "title red" else h["c"].split()[-1] if h["c"] else ""
            label(x, y, w, hh, h["l"], _COL.get(color, "#000000"), 16 if h["c"] == "name" else 13 if h["c"] in ("title", "title red") else 12,
                  True, bool(h.get("it")), bool(h.get("rot")))
            ci += h["cs"]
    # qatorlar
    y = hy[-1]

    def line(name, vals, total=False):
        nonlocal y
        rect(PAD, y, NAME_W, ROW_H, "#FFE699" if total else "#FFFFFF")
        label(PAD, y, NAME_W, ROW_H, name, size=13 if total else 12, bold=total, align="center" if total else "left", pad=7)
        for i, c in enumerate(tb["cols"]):
            bg = "#FFE699" if total else "#FFFDEF" if c.get("cream") else "#FFFFFF"
            x = PAD + NAME_W + i * COL_W
            rect(x, y, COL_W, ROW_H, bg)
            v = vals.get(c["k"], 0)
            if v:
                label(x, y, COL_W, ROW_H, f"{int(v):,}".replace(",", " "), _COL[c.get("c", "")], 12, True, align="right", pad=8)
        y += ROW_H

    line("Jami", tb["total"], True)
    for r in tb["rows"]:
        line(r["name"], r["v"])
    bio = BytesIO()
    img.save(bio, "PNG", optimize=True)
    return bio.getvalue()


# ----------------------------------------------------------------------------------------- papkalar
def folder(end: date):
    return app_settings.data_dir / "daily" / end.isoformat()
