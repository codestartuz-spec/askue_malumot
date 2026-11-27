"""Respublika dinamikasi: PDF'dan o'qish, solishtirish, yuklab olish, Telegramga yuborish (umumiy fabrika: pdf_reports.py)."""
import re
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..models import RepublicReport
from ..services import filenames as FN
from ..services import republic as R
from ..settings_store import app_cfg
from .pdf_reports import MIME, Kind, Parsed, SendIn, make_router  # noqa: F401  (MIME/SendIn boshqa joylar uchun)


def _parse(rep: dict, filename: str) -> Parsed:
    if rep.get("__is_ag"):
        raise HTTPException(400, "Bu AG dinamikasi PDF'i. «Ma'lumot yuklash» → «AG dinamikasi» bo'limidan yuklang")
    if not rep["pages"]:
        raise HTTPException(400, "PDF ichidan «Жами» (viloyat) qatori topilmadi — to'g'ri fayl ekanini tekshiring")
    end = rep["end"]
    if not end:
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\D*$", re.sub(r"\.pdf$", "", filename or "", flags=re.I))
        end = date(int(m[3]), int(m[2]), int(m[1])) if m else None
    if not end:
        raise HTTPException(400, "PDF ichidan sana aniqlanmadi")
    return Parsed(end, rep["start"], {"pages": rep["pages"]}, len(rep["pages"]))


def _view(pages, ad, bd, start):
    return {"pages": pages}


def _render(pages, fmt, ad, bd, start):
    from ..services import reports as RP
    items = [(p["key"], {"rows": p["rows"], "total": {"cur": p["cur"], "base": p["base"]}, "base": p["from"], "to": p["to"]})
             for p in pages]
    blob = (RP.build_pdf if fmt == "pdf" else RP.build_xlsx)(items, app_cfg("region_name"), "Hudud nomi")
    return FN.file_name("fn_republic", fmt, bd, ad or start), blob


def _orig(bd, start, saved):
    return FN.file_name("fn_republic_orig", "pdf", bd, start, asl=re.sub(r"\.pdf$", "", saved or "", flags=re.I) or "Qashqadaryo_HETK_dynamic")


KIND = Kind(
    key="republic", model=RepublicReport, missing_msg="Hali respublika PDF'i yuklanmagan",
    audit=("respublika_yuklash", "respublika_ochirish", "telegram_respublika"), post_title="Qashqadaryo dinamikasi",
    parse=_parse, count=lambda d: len(d.get("pages", [])),
    default_start=lambda end: date(end.year, end.month, 1),
    compare=lambda a, b, base, to, ref=None: R.compare(a, b, base, to, ref), view=_view, ref_start=True, render=_render, orig=_orig)
router = make_router(KIND)


def upgrade_stored() -> int:
    """Eski yuklangan PDF'larni (faqat Jami qatori saqlangan) tuman qatorlari bilan qayta o'qiydi."""
    n = 0
    folder = settings.data_dir / "republic"
    with SessionLocal() as db:
        for r in KIND.dates(db):
            if any(p.get("rows") for p in r.data.get("pages", [])):
                continue
            f = folder / f"{r.end_date.isoformat()}.pdf"
            if not f.exists():
                continue
            try:
                rep = R.parse_report(f.read_bytes())
            except Exception:  # noqa: BLE001
                continue
            if rep["pages"]:
                r.data = {"pages": rep["pages"]}
                n += 1
        db.commit()
    return n
