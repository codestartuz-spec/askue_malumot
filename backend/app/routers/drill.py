import io
import re
from datetime import datetime

import xlsxwriter
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import has_perm, need
from ..metrics import METER_SPEC, TR_SPEC
from ..models import User

router = APIRouter(prefix="/drill", tags=["drill"])

CTYPE = {1: "Ulgurji", 2: "Aholi", 3: "Balans"}
EXPORT_LIMIT = 300_000
MAX_OFFSET = 500_000


def _scope(prefix: str, esp_id, brigade_id, params: dict) -> list[str]:
    conds = []
    if esp_id:
        conds.append(f"{prefix}esp_id=:esp")
        params["esp"] = esp_id
    if brigade_id is not None:
        if brigade_id == 0:
            conds.append(f"{prefix}brigade_id IS NULL")
        else:
            conds.append(f"{prefix}brigade_id=:brig")
            params["brig"] = brigade_id
    return conds


def _xlsx(headers: list[str], rows, sheet: str) -> io.BytesIO:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "constant_memory": True})
    ws = wb.add_worksheet(sheet[:30])
    hf = wb.add_format({"bold": True, "bg_color": "#0B3B8C", "font_color": "#FFFFFF", "border": 1})
    for i, h in enumerate(headers):
        ws.write(0, i, h, hf)
        ws.set_column(i, i, max(12, min(40, len(h) + 6)))
    for r, row in enumerate(rows, start=1):
        for c, v in enumerate(row):
            ws.write(r, c, v)
    ws.freeze_panes(1, 0)
    wb.close()
    buf.seek(0)
    return buf


def _stream(buf: io.BytesIO, name: str):
    from urllib.parse import quote
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


def _fname(title: str, fallback: str) -> str:
    t = re.sub(r'[\\/:*?"<>|\r\n]+', " ", title or "").strip(" .")
    t = re.sub(r"\s+", " ", t)[:110]
    return f"{t or fallback} — {datetime.now():%d.%m.%Y %H-%M}.xlsx"


@router.get("/tr")
def drill_tr(metric: str, name: str = "", esp_id: int | None = None, brigade_id: int | None = None, q: str = "",
             page: int = 1, size: int = 50, export: bool = False,
             user: User = Depends(need("drill.view")), db: Session = Depends(get_db)):
    if metric not in TR_SPEC:
        raise HTTPException(400, "Noma'lum ko'rsatkich")
    if export and not has_perm(user, "export"):
        raise HTTPException(403, "Eksport uchun ruxsat yo'q")
    params: dict = {}
    conds = [f"({TR_SPEC[metric]})"] + _scope("t.", esp_id, brigade_id, params)
    if q.strip():
        conds.append("(t.tp_no LIKE :q OR t.dcu LIKE :q OR t.substation LIKE :q OR t.feeder LIKE :q)")
        params["q"] = f"%{q.strip()}%"
    where = " AND ".join(conds)
    total = db.execute(text(f"SELECT COUNT(*) FROM trs t WHERE {where}"), params).scalar() or 0
    base = ("SELECT t.id, e.label AS esp, t.tp_no, t.substation, t.feeder, t.dcu, t.state, t.obx_level, "
            "t.lv, t.attached, t.offline, t.offline3, b.name AS brigade, t.brigade_id, t.lat, t.lon "
            "FROM trs t JOIN esps e ON e.id=t.esp_id LEFT JOIN brigades b ON b.id=t.brigade_id "
            f"WHERE {where} ORDER BY e.sort, t.id")
    lv_names = {0: "", 1: "0%", 2: "1-30%", 3: "30-50%", 4: "50-80%", 5: "80-100%"}
    if export:
        if total > EXPORT_LIMIT:
            raise HTTPException(400, f"Eksport uchun juda ko'p yozuv ({total}). Filtrni toraytiring")
        rows = ((r["esp"], r["tp_no"], r["substation"], r["feeder"], r["dcu"] or "",
                 r["brigade"] or "Biriktirilmagan",
                 "Online" if r["state"] == 1 else "Offline" if r["state"] == 2 else "",
                 r["obx_level"] if r["obx_level"] is not None else "", lv_names[r["lv"]])
                for r in db.execute(text(base), params).mappings())
        buf = _xlsx(["Tuman", "TP", "Podstansiya", "Fider", "DCU", "Brigada", "Holati", "Obxod %",
                     "Obxod darajasi"], rows, "Konsentratorlar")
        return _stream(buf, _fname(name, "Konsentratorlar"))
    size = max(10, min(size, 200))
    offset = (max(page, 1) - 1) * size
    if offset > MAX_OFFSET:
        raise HTTPException(400, "Qidiruv yoki filtrdan foydalaning")
    items = [dict(r) | {"lv_name": lv_names[r["lv"]]} for r in db.execute(
        text(base + " LIMIT :lim OFFSET :off"), params | {"lim": size, "off": offset}).mappings()]
    return {"total": total, "page": page, "size": size, "items": items}


@router.get("/meters")
def drill_meters(metric: str, name: str = "", esp_id: int | None = None, brigade_id: int | None = None, q: str = "",
                 page: int = 1, size: int = 50, export: bool = False,
                 user: User = Depends(need("drill.view")), db: Session = Depends(get_db)):
    if metric not in METER_SPEC:
        raise HTTPException(400, "Noma'lum ko'rsatkich")
    if export and not has_perm(user, "export"):
        raise HTTPException(403, "Eksport uchun ruxsat yo'q")
    params: dict = {}
    conds = [f"({METER_SPEC[metric]})"] + _scope("m.", esp_id, brigade_id, params)
    qs = q.strip()
    if qs:
        if qs.isdigit():
            conds.append("(m.meter_no LIKE :q1 OR m.account LIKE :q1)")
            params["q1"] = f"{qs}%"
        else:
            conds.append("(m.name LIKE :q2 OR m.address LIKE :q2)")
            params["q2"] = f"%{qs}%"
    where = " AND ".join(conds)
    total = db.execute(text(f"SELECT COUNT(*) FROM meters m WHERE {where}"), params).scalar() or 0
    base = ("SELECT m.meter_no, m.account, m.name, m.address, m.tp_no, e.label AS esp, b.name AS brigade, "
            "m.ctype, m.mtype, m.link, m.last_poll, m.days, m.status, m.lat, m.lon "
            "FROM meters m JOIN esps e ON e.id=m.esp_id LEFT JOIN brigades b ON b.id=m.brigade_id "
            f"WHERE {where} ORDER BY m.meter_no")
    if export:
        if total > EXPORT_LIMIT:
            raise HTTPException(400, f"Eksport uchun juda ko'p yozuv ({total}). Filtrni toraytiring")
        rows = ((r["esp"], r["brigade"] or "Biriktirilmagan", r["tp_no"], r["account"], r["meter_no"],
                 r["name"], r["address"], CTYPE.get(r["ctype"], ""), r["mtype"], r["link"],
                 r["last_poll"].strftime("%Y-%m-%d %H:%M") if r["last_poll"] else "",
                 r["days"] if r["days"] is not None else "")
                for r in db.execute(text(base), params).mappings())
        buf = _xlsx(["Tuman", "Brigada", "TP", "Hisob raqam", "Hisoblagich", "Abonent", "Manzil",
                     "Turi", "Hisoblagich turi", "Aloqa", "Oxirgi obxod", "Kun"], rows, "Hisoblagichlar")
        return _stream(buf, _fname(name, "Hisoblagichlar"))
    size = max(10, min(size, 200))
    offset = (max(page, 1) - 1) * size
    if offset > MAX_OFFSET:
        raise HTTPException(400, "Qidiruv yoki filtrdan foydalaning")
    items = []
    for r in db.execute(text(base + " LIMIT :lim OFFSET :off"),
                        params | {"lim": size, "off": offset}).mappings():
        d = dict(r)
        d["ctype_name"] = CTYPE.get(r["ctype"], "")
        d["last_poll"] = r["last_poll"].strftime("%Y-%m-%d %H:%M") if r["last_poll"] else None
        items.append(d)
    return {"total": total, "page": page, "size": size, "items": items}
