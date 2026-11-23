"""Kunlik topshiriq bo'limi: 5 ta Excel fayldan jadvallar va xodimlar bo'yicha topshiriq faylini tayyorlash.

Boshqa bo'limlardan to'liq ajratilgan: o'z jadvali (daily_batches), o'z papkasi (data/daily), o'z sozlamalari (daily_settings).

Fayllar:  area (AreaInformationReport) · status (CommissioningStatus) · direct (DirectMeter)
          nometer (NoMeterData) · online (Online_Device_Monitoring_Report — faqat offline qurilmalar)

Ustun nomlari dastur tiliga bog'liq bo'lishi mumkin, shuning uchun ustunlar sarlavha matni (ru/en) bo'yicha,
topilmasa — standart o'rni bo'yicha aniqlanadi."""
import json
import re
from collections import defaultdict
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


# kalit: ([sarlavha variantlari], standart o'rin)
SPEC = {
    "area": {"ncols": 16, "title": ["area information report"], "file": ["areainformation", "area_information"],
             "cols": {"esp": (["esp name", "название эсп", "эсп"], 4), "ss": (["substation", "подстанция"], 6),
                      "fd": (["feeder", "фидер"], 8), "tr": (["tr", "тп"], 10),
                      "mgr": (["manager name", "имя менеджера"], 12)}},
    "status": {"ncols": 11, "title": ["commissioning status", "отчет о статусе ввода"], "file": ["commissioning"],
               "cols": {"esp": (["название эсп", "esp name"], 1),
                        "tr": (["номер трансформатора", "transformer no.", "transformer number"], 2),
                        "dcu": (["номер концентратора данных", "data concentrator no.", "data concentrator number"], 3),
                        "pcs": (["установлено(pcs)", "installed(pcs)"], 7),
                        "poll": (["однодневный опрос %", "one-day polling %", "one day polling %"], 10)}},
    "direct": {"ncols": 13, "title": ["сведения о прямых подключениях", "direct"], "file": ["directmeter", "direct_meter"],
               "cols": {"esp": (["esp name", "название эсп"], 1), "ss": (["substation", "подстанция"], 3),
                        "fd": (["feeder", "фидер"], 4), "tr": (["tr", "тп"], 5), "meter": (["meter no.", "номер счетчика"], 6),
                        "acc": (["account id", "лицевой счет потребителя"], 7), "ctype": (["customer type", "тип потребителя"], 8),
                        "name": (["name", "имя потребителя"], 9), "addr": (["customer address", "адрес установки"], 10),
                        "mtype": (["meter type", "тип счетчика"], 11), "gps": (["gps"], 12)}},
    "nometer": {"ncols": 16, "title": ["нет информации счетчика", "no meter"], "file": ["nometer", "no_meter"],
                "cols": {"esp": (["эсп", "esp"], 1), "ss": (["подстанция", "substation"], 2), "fd": (["фидер", "feeder"], 3),
                         "tr": (["номер трансформатора", "transformer no.", "transformer number"], 4),
                         "acc": (["лицевой счет потребителя", "account id"], 5), "ctype": (["тип потребителя", "customer type"], 6),
                         "name": (["имя потребителя", "customer name"], 7), "meter": (["номер счетчика", "meter no."], 8),
                         "link": (["тип связи", "communication type"], 9), "mgr": (["имя менеджера", "manager name"], 10),
                         "days": (["несобранный период (день)", "uncollected period (day)"], 12),
                         "time": (["несобранный период (время)", "uncollected period (time)"], 13),
                         "gps": (["gps(x,y)", "gps"], 14), "addr": (["адрес установки", "installation address"], 15)}},
    "online": {"ncols": 19, "title": ["отчет по мониторингу сетевых", "device network", "online device"], "file": ["online_device", "onlinedevice"],
               "cols": {"esp": (["эсп", "esp"], 0), "ss": (["подстанция", "substation"], 1), "fd": (["фидер", "feeder"], 2),
                        "tr": (["тп", "tr"], 3), "dev": (["№ устройства", "device no.", "device no"], 5),
                        "st": (["статус", "status"], 6), "time": (["время онлайна/офлайна", "online/offline time"], 7),
                        "lat": (["широта", "latitude"], 9), "lon": (["долгота", "longitude"], 10),
                        "mgr": (["имя менеджера", "manager name"], 15)}},
}


class DailyError(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato."""


# ----------------------------------------------------------------------------------------- o'qish
def _header_pos(row, kind: str) -> dict[str, int]:
    """Bitta qator bo'yicha ustun o'rinlari: {kalit: indeks} (sarlavha bo'yicha topilganlar)."""
    cells = [_n(c) for c in row]
    pos = {}
    for key, (names, _d) in SPEC[kind]["cols"].items():
        for i, c in enumerate(cells):
            if c in names:
                pos[key] = i
                break
    return pos


def _peek(src, limit: int = 12) -> list[tuple]:
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        ws.reset_dimensions()      # ba'zi eksportlarda o'lcham noto'g'ri yoziladi (1x1)
        return [tuple(r) for _i, r in zip(range(limit), ws.iter_rows(values_only=True))]
    finally:
        wb.close()


def detect(src, filename: str = "") -> tuple[str, int]:
    """Fayl turini sarlavha, nom va ustunlar soniga qarab aniqlaydi → (tur, sarlavha qatori indeksi)."""
    try:
        rows = _peek(src)
    except Exception as e:  # noqa: BLE001
        raise DailyError(f"«{filename}» — Excel (.xlsx) faylni o'qib bo'lmadi") from e
    title = _n(rows[0][0]) if rows and rows[0] else ""
    fname = re.sub(r"[^a-z0-9_]", "", (filename or "").lower())
    best = (0, None, 0)
    for kind, sp in SPEC.items():
        score = 5 * any(t in title for t in sp["title"]) + 5 * any(t in fname for t in sp["file"])
        hrow, hits = 0, 0
        for i, r in enumerate(rows):
            h = len(_header_pos(r, kind))
            if h > hits:
                hrow, hits = i, h
        score += hits
        if score > best[0]:
            best = (score, kind, hrow)
    if not best[1] or best[0] < 4:
        raise DailyError(f"«{filename}» — fayl turi aniqlanmadi (5 ta kutilgan fayldan biri emas)")
    return best[1], best[2]


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


def read(src, kind: str, hrow: int | None = None) -> list[dict]:
    """Faylni qator-qator o'qiydi: [{kalit: matn}] (ESP nomi bo'sh qatorlar tashlanadi)."""
    sp = SPEC[kind]
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        ws.reset_dimensions()
        it = ws.iter_rows(values_only=True)
        head, out, idx = None, [], {}
        for i, r in enumerate(it):
            if head is None:
                if hrow is not None and i < hrow:
                    continue
                pos = _header_pos(r, kind)
                if hrow is None and len(pos) < 3:
                    continue
                head = r
                miss = [k for k in sp["cols"] if k not in pos]
                if miss and len(r) != sp["ncols"]:
                    names = ", ".join(sp["cols"][k][0][0] for k in miss)
                    raise DailyError(f"{LABEL[kind]}: kerakli ustunlar topilmadi ({names})")
                idx = {k: pos.get(k, sp["cols"][k][1]) for k in sp["cols"]}
                continue
            if not r or idx["esp"] >= len(r):
                continue
            row = {k: _s(r[j]) if j < len(r) else "" for k, j in idx.items()}
            if row["esp"] and row["esp"].lower() not in ("total", "итого", "всего"):
                out.append(row)
        if head is None:
            raise DailyError(f"{LABEL[kind]}: sarlavha qatori topilmadi")
        return out
    finally:
        wb.close()


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


def file_name(s: dict, which: str, end) -> str:
    fk, tk = next((f, t) for k, f, t in FILE_KEYS if k == which)
    ctx = FN.context(end, None, hudud=s["region"], nom=s[tk])
    return FN.render(s[fk], ctx, "xlsx", s[tk].replace(" ", "_") or "Hisobot")


def names_example(s: dict) -> dict:
    return {k: file_name(s, k, "2026-11-23") for k, _f, _t in FILE_KEYS}


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


# ----------------------------------------------------------------------------------------- Excel: topshiriq
SHEETS = [
    ("Offline kontsentratorlar", "offline", ["Qurilma raqami", "Offline vaqti", "Offline (kun)"]),
    ("Aloqasiz hisoblagichlar", "nometer", ["Hisob raqami", "Iste'molchi", "Iste'molchi turi", "Hisoblagich raqami",
                                            "Aloqa turi", "Aloqasiz (kun)", "Manzil"]),
    ("Primichka", "direct", ["Hisob raqami", "Iste'molchi", "Iste'molchi turi", "Hisoblagich raqami", "Hisoblagich turi", "Manzil"]),
]


WIDTHS = {"offline": [18, 20, 12], "nometer": [14, 30, 16, 16, 10, 12, 40], "direct": [14, 30, 16, 16, 18, 40]}


def _task_rows(end: date, data: dict, order: list[str]) -> dict[str, list[dict]]:
    mgr = {}
    for r in data["area"]:
        mgr.setdefault((r["esp"], r["ss"], r["fd"], r["tr"]), r["mgr"])
    rank = {e: i for i, e in enumerate(order)}

    def base(r):
        return {"esp": r["esp"], "ss": r["ss"], "fd": r["fd"], "tr": r["tr"],
                "mgr": mgr.get((r["esp"], r["ss"], r["fd"], r["tr"])) or r.get("mgr", "")}

    out = {"offline": [], "nometer": [], "direct": []}
    seen = set()
    for r in data["online"]:
        if _n(r.get("st")) in ("online", "онлайн") or ("o", r["dev"]) in seen:
            continue
        seen.add(("o", r["dev"]))
        t = _dt(r["time"])
        loc = (_num(r["lat"]), _num(r["lon"]))
        out["offline"].append({**base(r), "loc": loc if all(loc) else None,
                               "x": [r["dev"], t.strftime("%d.%m.%Y %H:%M:%S") if t else r["time"],
                                     (end - t.date()).days if t else ""]})
    for r in data["nometer"]:
        k = ("n", r["meter"] or r["acc"])
        if k in seen and r["meter"]:
            continue
        seen.add(k)
        out["nometer"].append({**base(r), "loc": _gps(r["gps"]),
                               "x": [r["acc"], r["name"], r["ctype"], r["meter"], r["link"],
                                     int(_num(r["days"])) if _num(r["days"]) is not None else "", r["addr"]]})
    for r in data["direct"]:
        k = ("d", r["meter"] or r["acc"])
        if k in seen and r["meter"]:
            continue
        seen.add(k)
        out["direct"].append({**base(r), "loc": _gps(r["gps"]),
                              "x": [r["acc"], r["name"], r["ctype"], r["meter"], r["mtype"], r["addr"]]})
    for rows in out.values():      # xodim bo'yicha: bo'sh xodimlar oxirida
        rows.sort(key=lambda x: (not x["mgr"], x["mgr"].lower(), rank.get(x["esp"], 999), _nat(x["ss"]), _nat(x["fd"]), _nat(x["tr"])))
    return out


def task_xlsx(end: date, data: dict, s: dict) -> tuple[bytes, dict]:
    rows = _task_rows(end, data, s["esp_order"])
    bio = BytesIO()
    wb = xlsxwriter.Workbook(bio, {"in_memory": True, "strings_to_urls": False, "strings_to_numbers": False})
    F = lambda **kw: wb.add_format({"font_name": "Calibri", "font_size": 11, "border": 1, "border_color": LINE, "valign": "vcenter", **kw})  # noqa: E731
    head = F(bold=True, bg_color="#DDEBF7", align="center", text_wrap=True)
    cell, link = F(), F(font_color="#0563C1", underline=1)
    ttl = wb.add_format({"font_name": "Calibri", "font_size": 13, "bold": True})
    counts = {}
    for name, key, extra in SHEETS:
        ws = wb.add_worksheet(name)
        data_rows = rows[key]
        counts[key] = len(data_rows)
        cols = ["#", "Tuman", "Podstansiya", "Fider", "TP raqami", *extra, "Joylashuv", "Xodim(lar)"]
        ws.write(0, 0, f"{s['task_title']} — {end:%d.%m.%Y} — {name} ({len(data_rows)} ta)", ttl)
        for j, c in enumerate(cols):
            ws.write(1, j, c, head)
        for j, w in enumerate([6, 18, 26, 20, 10] + WIDTHS[key] + [22, 48]):
            ws.set_column(j, j, w)
        for i, r in enumerate(data_rows):
            rr = 2 + i
            ws.write_number(rr, 0, i + 1, cell)
            for j, v in enumerate([r["esp"], r["ss"], r["fd"], r["tr"], *r["x"]], 1):
                if isinstance(v, int):
                    ws.write_number(rr, j, v, cell)
                else:
                    ws.write_string(rr, j, v or "", cell)
            lc = 5 + len(extra)
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
    wb.close()
    return bio.getvalue(), counts


# ----------------------------------------------------------------------------------------- papkalar
def folder(end: date):
    return app_settings.data_dir / "daily" / end.isoformat()
