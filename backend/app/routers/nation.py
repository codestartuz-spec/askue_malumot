"""Respublika dinamikasi (barcha viloyatlar): R-Dynamic PDF'dan o'qish, solishtirish, yuklab olish, Telegramga
(PDF / Excel / asl PDF / jadval rasmlari) yuborish. Umumiy fabrika: pdf_reports.py. Qashqadaryo dinamikasi
(routers/republic.py) bilan bir xil jadval tuzilmasi, lekin qatorlar — viloyatlar."""
import io
import re
from datetime import date

from fastapi import HTTPException

from ..models import NationReport
from ..services import filenames as FN
from ..services import nation as N
from .pdf_reports import Kind, Parsed, make_router

SCOPE = "Respublika"
FIRST = "Viloyat nomi"


def _parse(rep: dict, filename: str) -> Parsed:
    if rep.get("__is_ag"):
        raise HTTPException(400, "Bu AG dinamikasi PDF'i. «Ma'lumot yuklash» → «AG dinamikasi» bo'limidan yuklang")
    if not rep.get("pages"):
        raise HTTPException(400, "Bu respublika (barcha viloyatlar) PDF'i emas — «Жами» va 14 viloyat qatori topilmadi. "
                                 "Qashqadaryo PDF'ini «Qashqadaryo dinamikasi» bo'limidan yuklang")
    end = rep["end"]
    if not end:
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\D*$", re.sub(r"\.pdf$", "", filename or "", flags=re.I))
        end = date(int(m[3]), int(m[2]), int(m[1])) if m else None
    if not end:
        raise HTTPException(400, "PDF ichidan sana aniqlanmadi")
    return Parsed(end, rep["start"], {"pages": rep["pages"]}, len(rep["pages"]))


def _items(pages):
    return [(p["key"], {"rows": p["rows"], "total": {"cur": p["cur"], "base": p["base"]}, "base": p["from"], "to": p["to"]})
            for p in pages]


def _render(pages, fmt, ad, bd, start):
    from ..services import reports as RP
    blob = (RP.build_pdf if fmt == "pdf" else RP.build_xlsx)(_items(pages), SCOPE, FIRST)
    return FN.file_name("fn_nation", fmt, bd, ad or start), blob


def _images(pages, ad, bd, start):
    """Har bir jadval — alohida PNG (PDF sahifasi rasmga olinadi, dizayn PDF bilan bir xil)."""
    import pypdfium2 as pdfium
    from PIL import Image, ImageChops
    from ..services import reports as RP
    out = []
    for p, it in zip(pages, _items(pages)):
        pdf = pdfium.PdfDocument(RP.build_pdf([it], SCOPE, FIRST))
        page = pdf[0]
        img = page.render(scale=2.4).to_pil().convert("RGB")
        page.close()
        pdf.close()
        box = ImageChops.difference(img, Image.new("RGB", img.size, "white")).getbbox()     # oq chetlarni kesish
        if box:
            pad = 28
            img = img.crop((max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, img.width), min(box[3] + pad, img.height)))
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        out.append((FN.file_name("fn_nation_png", "png", bd, ad or start, sahifa=FN.part(p["short"])), buf.getvalue()))
    return out


def _orig(bd, start, saved):
    return FN.file_name("fn_nation_orig", "pdf", bd, start, asl=re.sub(r"\.pdf$", "", saved or "", flags=re.I) or "R-Dynamic")


KIND = Kind(
    key="nation", model=NationReport, missing_msg="Hali respublika PDF'i yuklanmagan",
    audit=("nation_yuklash", "nation_ochirish", "telegram_nation"), post_title="Respublika dinamikasi",
    parse=_parse, count=lambda d: len(d.get("pages", [])),
    default_start=lambda end: date(end.year, end.month, 1),
    compare=lambda a, b, base, to: N.compare(a, b, base, to), view=lambda pages, ad, bd, start: {"pages": pages},
    render=_render, orig=_orig, images=_images)
router = make_router(KIND)
