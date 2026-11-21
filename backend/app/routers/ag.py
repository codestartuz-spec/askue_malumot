"""AG dinamikasi: Respublika bilan bir xil jarayon (umumiy fabrika: pdf_reports.py)."""
from datetime import date

from fastapi import HTTPException

from ..models import AgReport
from ..services import ag as A
from ..settings_store import app_cfg
from .pdf_reports import Kind, Parsed, make_router


def _parse(rep: dict, _filename: str) -> Parsed:
    if not rep.get("end"):
        raise HTTPException(400, "PDF ichidan sana aniqlanmadi")
    return Parsed(rep["end"], rep["start"], {k: rep[k] for k in ("title", "region", "total", "rows")}, len(rep["rows"]))


def _render(res, fmt, ad, bd, start):
    from ..services import ag_report as AR
    blob = (AR.build_pdf if fmt == "pdf" else AR.build_xlsx)(res)
    return (f"AG_dinamikasi_{bd.isoformat()}.{fmt}", blob,
            f"📊 AG dinamikasi — {res['region']}\n📅 {(ad or start):%d.%m.%Y} – {bd:%d.%m.%Y}")


def _orig(bd, start, saved):
    return (saved or f"Qashqadaryo_HETK_AG_{bd.isoformat()}.pdf",
            f"📄 AG dinamikasi (asl nusxa)\n📅 {start:%d.%m.%Y} – {bd:%d.%m.%Y}")


KIND = Kind(
    key="ag", model=AgReport, missing_msg="Hali AG PDF'i yuklanmagan",
    audit=("ag_yuklash", "ag_ochirish", "telegram_ag"), post_title="AG dinamikasi",
    parse=_parse, count=lambda d: len(d.get("rows", [])),
    default_start=lambda end: date.fromisoformat(app_cfg("ag_start_date")),
    compare=A.compare, view=lambda res, ad, bd, start: dict(res), render=_render, orig=_orig)
router = make_router(KIND)
