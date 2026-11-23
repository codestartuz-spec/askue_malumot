"""Hisobot fayllari nomi (yuklab olish va Telegram). Nom shablonlari Sozlamalarda o'zgartiriladi.

Shablon: oddiy matn + {o'rin_belgilar}. Kengaytma (.pdf/.xlsx) avtomatik qo'shiladi.
Xavfsizlik: shablon str.format bilan emas, faqat {nom} ni qidirib almashtirish bilan ishlaydi; fayl nomidagi
taqiqlangan belgilar (\\ / : * ? " < > |) va boshqaruv belgilari olib tashlanadi, uzunlik cheklanadi."""
import re
from datetime import date, datetime

PLACEHOLDERS = {
    "hudud": "hudud (filial) nomi",
    "nom": "tuman nomi (tuman hisobotida)",
    "sana": "hisobot sanasi, 2026-11-23",
    "sana_dmy": "hisobot sanasi, 23.11.2026",
    "dan": "solishtirish boshlanish sanasi, 2026-11-01",
    "dan_dmy": "solishtirish boshlanish sanasi, 01.11.2026",
    "yil": "yil, 2026",
    "oy": "oy raqami, 11",
    "kun": "kun raqami, 23",
    "asl": "yuklangan asl fayl nomi (kengaytmasiz)",
}
_BASE = ("hudud", "sana", "sana_dmy", "dan", "dan_dmy", "yil", "oy", "kun")

# kalit, yorliq, boshlang'ich shablon, ruxsat etilgan o'rin belgilar, zaxira (shablon bo'sh natija bersa)
FILES = [
    ("fn_daily_region", "Kunlik dinamika — hudud hisoboti (PDF/Excel)", "Dinamika_{hudud}_{sana}", _BASE),
    ("fn_daily_district", "Kunlik dinamika — tuman hisoboti (PDF/Excel)", "Dinamika_{nom}_{sana}", _BASE + ("nom",)),
    ("fn_republic", "Respublika dinamikasi (PDF/Excel)", "Respublika_dinamikasi_{sana}", _BASE),
    ("fn_republic_orig", "Respublika dinamikasi — asl PDF", "{asl}", _BASE + ("asl",)),
    ("fn_ag", "AG dinamikasi (PDF/Excel)", "AG_dinamikasi_{sana}", _BASE),
    ("fn_ag_orig", "AG dinamikasi — asl PDF", "{asl}", _BASE + ("asl",)),
]
ALLOWED = {k: set(p) for k, _l, _d, p in FILES}
DEFAULT = {k: d for k, _l, d, _p in FILES}
_FALLBACK = {"fn_daily_region": "Dinamika", "fn_daily_district": "Dinamika", "fn_republic": "Respublika_dinamikasi",
             "fn_republic_orig": "Respublika_dinamikasi", "fn_ag": "AG_dinamikasi", "fn_ag_orig": "AG_dinamikasi"}
_PH = re.compile(r"\{([^{}]*)\}")
_BAD = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")
MAX_LEN = 120


def _d(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def part(s: str) -> str:
    """Hudud/tuman nomi fayl nomiga: tutuq belgilari olib tashlanadi, bo'shliq → «_» (Muborak t. → Muborak_t)."""
    s = re.sub(r"[‘’ʻʼ'`]", "", s or "")
    return re.sub(r"_+", "_", _BAD.sub("_", re.sub(r"\s+", "_", s))).strip("_. ")


def context(end, start=None, **extra) -> dict[str, str]:
    e, b = _d(end), _d(start)
    ctx = {"yil": f"{e:%Y}", "oy": f"{e:%m}", "kun": f"{e:%d}", "sana": e.isoformat(), "sana_dmy": f"{e:%d.%m.%Y}"} if e else {}
    if b:
        ctx.update(dan=b.isoformat(), dan_dmy=f"{b:%d.%m.%Y}")
    elif e:
        ctx.update(dan=e.isoformat(), dan_dmy=f"{e:%d.%m.%Y}")
    for k, v in extra.items():
        ctx[k] = part(v) if k in ("hudud", "nom") else _BAD.sub("_", str(v or "")).strip(" ._")
    return ctx


def render(template: str, ctx: dict[str, str], ext: str, fallback: str = "Hisobot") -> str:
    stem = _PH.sub(lambda m: ctx.get(m.group(1), ""), template or "")
    stem = _BAD.sub("", stem)
    stem = re.sub(r"\.(pdf|xlsx)$", "", stem.strip(), flags=re.I)
    stem = re.sub(r"_{2,}", "_", stem).strip(" ._")[:MAX_LEN].strip(" ._")
    return f"{stem or fallback}.{ext}"


def validate(key: str, template: str) -> str | None:
    """Xato matni yoki None. Noma'lum {o'rin_belgi} yoki bo'sh natija rad etiladi."""
    if key not in ALLOWED:
        return "Noma'lum fayl turi"
    t = (template or "").strip()
    if not t:
        return "Shablon bo'sh bo'lmasin"
    if len(t) > 120:
        return "Shablon juda uzun (120 belgigacha)"
    if t.count("{") != t.count("}"):
        return "Qavs { } juft bo'lishi kerak"
    bad = sorted({n for n in _PH.findall(t) if n not in ALLOWED[key]})
    if bad:
        return "Bu fayl uchun noma'lum o'rin belgi: " + ", ".join("{" + b + "}" for b in bad)
    if not re.sub(r"[\s._]", "", _BAD.sub("", _PH.sub("x", t))):
        return "Shablon fayl nomi bo'lib qolmaydi"
    return None


def sample_ctx(region: str) -> dict[str, str]:
    return context("2026-11-23", "2026-11-01", hudud=region, nom="Muborak t.", asl="Qashqadaryo_HETK_dynamic")


def preview(key: str, template: str, region: str, ext: str = "pdf") -> str:
    return render(template, sample_ctx(region), ext, _FALLBACK[key])


def file_name(key: str, ext: str, end, start=None, **extra) -> str:
    """Saqlangan shablon bo'yicha fayl nomi (Sozlamalardan)."""
    from ..settings_store import app_cfg
    extra.setdefault("hudud", app_cfg("region_name"))
    return render(app_cfg(key), context(end, start, **extra), ext, _FALLBACK[key])
