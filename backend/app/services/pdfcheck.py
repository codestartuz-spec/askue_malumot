"""PDF yuklash xavfsizligi.

1) Qabul qilishdan oldin (tez, baytlar ustida): kengaytma, hajm, %PDF- sarlavhasi, %%EOF, shifrlanmaganligi,
   xavfli elementlar (/JavaScript, /JS, /Launch, /EmbeddedFile, /OpenAction, /RichMedia, /XFA, /SubmitForm).
   Nomlardagi #xx ko'rinishidagi yashirish urinishlari ham ochib tekshiriladi.
2) O'qish (parse) alohida jarayonda, vaqt va xotira chegarasi bilan: buzuq/zararli PDF asosiy serverni
   qotirib qo'ya olmaydi."""
import json
import re
import subprocess
import sys
from datetime import date

from fastapi import HTTPException, UploadFile

from ..config import BASE, settings

FORBIDDEN = [b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/OpenAction", b"/RichMedia", b"/XFA",
             b"/SubmitForm", b"/ImportData"]
_HEX = re.compile(rb"#([0-9A-Fa-f]{2})")


def static_check(data: bytes) -> None:
    if not data.lstrip(b"\x00 \r\n\t")[:1024].startswith(b"%PDF-") and b"%PDF-" not in data[:1024]:
        raise HTTPException(400, "Bu haqiqiy PDF fayl emas (sarlavha topilmadi)")
    if b"%%EOF" not in data[-4096:]:
        raise HTTPException(400, "PDF fayl to'liq emas yoki shikastlangan (oxiri topilmadi)")
    flat = _HEX.sub(lambda m: bytes([int(m.group(1), 16)]), data)
    if b"/Encrypt" in flat:
        raise HTTPException(400, "Parol bilan himoyalangan PDF qabul qilinmaydi")
    for tok in FORBIDDEN:
        # to'liq nom bo'lishi uchun: /JS dan keyin harf bo'lmasligi kerak (/JSON kabi uchramasin)
        if re.search(re.escape(tok) + rb"(?![A-Za-z0-9])", flat):
            raise HTTPException(400, "PDF ichida faol kontent (skript/ilova) bor — bunday fayl qabul qilinmaydi")


def read_upload(file: UploadFile) -> bytes:
    """Fayl nomi, hajmi va tuzilmasini tekshirib baytlarni qaytaradi."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Faqat PDF fayl qabul qilinadi")
    limit = settings.max_pdf_mb * 1048576
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(400, f"Fayl juda katta ({settings.max_pdf_mb} MB dan oshmasin)")
    if len(data) < 200:
        raise HTTPException(400, "Fayl bo'sh yoki juda kichik")
    static_check(data)
    return data


# --- sanalarni JSON orqali o'tkazish
def _enc(o):
    if isinstance(o, date):
        return {"__d": o.isoformat()}
    raise TypeError(type(o))


def _dec(o):
    if "__d" in o:
        return date.fromisoformat(o["__d"])
    return o


def parse_isolated(kind: str, data: bytes) -> dict:
    """kind: 'republic' | 'ag' | 'nation'. Alohida Python jarayonida o'qiydi (python -I: begona kod yuklanmaydi)."""
    try:
        code = f"import sys; sys.path.insert(0, {str(BASE)!r}); from app.services.pdfcheck import _main; _main(sys.argv[1])"
        p = subprocess.run([sys.executable, "-I", "-c", code, kind], input=data, capture_output=True,
                           timeout=settings.pdf_parse_timeout, cwd=str(BASE))
    except subprocess.TimeoutExpired as e:
        raise HTTPException(400, f"PDF juda uzoq o'qildi ({settings.pdf_parse_timeout} soniya) — fayl qabul qilinmadi") from e
    out = p.stdout.decode("utf-8", "replace").strip().splitlines()
    last = out[-1] if out else ""
    if p.returncode != 0 or not last.startswith("{"):
        raise HTTPException(400, "PDF o'qib bo'lmadi. To'g'ri hisobot faylini yuklang")
    res = json.loads(last, object_hook=_dec)
    if "error" in res:
        raise HTTPException(400, res["error"])
    return res["ok"]


def _main(kind: str) -> None:
    try:
        import resource   # faqat Linux/macOS
        resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))
    except Exception:  # noqa: BLE001
        pass
    data = sys.stdin.buffer.read()
    try:
        import pdfplumber
        with pdfplumber.open(__import__("io").BytesIO(data)) as pdf:
            if len(pdf.pages) > settings.max_pdf_pages:
                raise ValueError(f"PDF sahifalari juda ko'p (>{settings.max_pdf_pages})")
        if kind == "ag":
            from . import ag
            res = ag.parse_pdf(data)
        elif kind == "nation":
            from . import nation
            res = nation.parse_report(data) if nation.looks_like(data) else {"start": None, "end": None, "pages": []}
        else:
            from . import ag, nation, republic
            if ag.looks_like_ag(data):
                res = {"__is_ag": True}
            elif nation.looks_like(data):
                res = {"__is_nation": True}
            else:
                res = republic.parse_report(data)
        print(json.dumps({"ok": res}, default=_enc, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": f"PDF o'qib bo'lmadi ({str(e)[:160]})"}, ensure_ascii=False))

