"""Audit jurnali: qidiruv, filtrlar, CSV/Excel eksport."""
import csv
import io
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..db import engine, get_db
from ..deps import need
from ..models import User

router = APIRouter(prefix="/audit", tags=["audit"])
MAX_EXPORT = 50000


def _where(q, user, action, ip, date_from, date_to) -> tuple[str, dict]:
    w, p = [], {}
    if q:
        w.append("(detail LIKE :q OR username LIKE :q OR action LIKE :q OR ip LIKE :q)")
        p["q"] = f"%{q.strip()[:100]}%"
    if user:
        w.append("username=:u")
        p["u"] = user
    if action:
        w.append("action=:a")
        p["a"] = action
    if ip:
        w.append("ip=:ip")
        p["ip"] = ip.strip()
    try:
        if date_from:
            p["df"] = datetime.combine(date.fromisoformat(date_from), datetime.min.time())
            w.append("created_at>=:df")
        if date_to:
            p["dt"] = datetime.combine(date.fromisoformat(date_to), datetime.min.time()) + timedelta(days=1)
            w.append("created_at<:dt")
    except ValueError as e:
        raise HTTPException(400, "Sana noto'g'ri (YYYY-MM-DD)") from e
    return (" WHERE " + " AND ".join(w)) if w else "", p


@router.get("")
def audit(page: int = 1, size: int = 50, q: str = "", user: str = "", action: str = "", ip: str = "",
          date_from: str = "", date_to: str = "", _: User = Depends(need("audit.view")), db: Session = Depends(get_db)):
    size = max(10, min(size, 200))
    where, p = _where(q, user, action, ip, date_from, date_to)
    total = db.execute(text(f"SELECT COUNT(*) FROM audit{where}"), p).scalar()
    rows = db.execute(text(f"SELECT id, username, action, detail, ip, created_at FROM audit{where} "
                           "ORDER BY id DESC LIMIT :l OFFSET :o"),
                      p | {"l": size, "o": (max(page, 1) - 1) * size}).mappings()
    return {"total": total, "items": [dict(r) | {"created_at": r["created_at"].isoformat()} for r in rows]}


@router.get("/facets")
def facets(_: User = Depends(need("audit.view")), db: Session = Depends(get_db)):
    """Filtr ro'yxatlari uchun: harakat turlari va foydalanuvchilar."""
    return {"actions": [r[0] for r in db.execute(text("SELECT DISTINCT action FROM audit ORDER BY action"))],
            "users": [r[0] for r in db.execute(text("SELECT DISTINCT username FROM audit WHERE username<>'' ORDER BY username"))]}


@router.get("/export")
def export(fmt: str = "csv", q: str = "", user: str = "", action: str = "", ip: str = "", date_from: str = "",
           date_to: str = "", me: User = Depends(need("audit.view")), _d: User = Depends(need("report.download")),
           db: Session = Depends(get_db)):
    if fmt not in ("csv", "xlsx"):
        raise HTTPException(400, "Noto'g'ri format")
    where, p = _where(q, user, action, ip, date_from, date_to)
    rows = db.execute(text(f"SELECT id, created_at, username, action, ip, detail FROM audit{where} "
                           "ORDER BY id DESC LIMIT :l"), p | {"l": MAX_EXPORT}).all()
    head = ["ID", "Vaqt", "Foydalanuvchi", "Harakat", "IP", "Tafsilot"]
    from .. import deps
    deps.log(db, me.username, "audit_eksport", f"{fmt}, {len(rows)} qator")
    db.commit()
    name = f"audit_{datetime.now():%Y%m%d_%H%M}.{fmt}"
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(head)
        for r in rows:
            w.writerow([r[0], r[1].strftime("%Y-%m-%d %H:%M:%S"), r[2], r[3], r[4] or "", _safe(r[5])])
        return Response(("﻿" + buf.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})
    import xlsxwriter
    bio = io.BytesIO()
    wb = xlsxwriter.Workbook(bio, {"in_memory": True, "strings_to_formulas": False})
    ws = wb.add_worksheet("Audit")
    hf = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
    for c, h in enumerate(head):
        ws.write(0, c, h, hf)
    for i, r in enumerate(rows, 1):
        ws.write_number(i, 0, r[0])
        ws.write_string(i, 1, r[1].strftime("%Y-%m-%d %H:%M:%S"))
        for c, v in enumerate((r[2], r[3], r[4] or "", r[5]), 2):
            ws.write_string(i, c, _safe(str(v)))
    ws.set_column(0, 0, 8); ws.set_column(1, 1, 19); ws.set_column(2, 4, 18); ws.set_column(5, 5, 90)
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, max(len(rows), 1), len(head) - 1)
    wb.close()
    return Response(bio.getvalue(), headers={"Content-Disposition": f'attachment; filename="{name}"'},
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _safe(v: str) -> str:
    """CSV/Excel formula in'ektsiyasidan himoya: =, +, -, @ bilan boshlansa oldiga ' qo'yiladi."""
    v = (v or "").replace("\r", " ").replace("\n", " ")
    return "'" + v if v[:1] in ("=", "+", "-", "@") else v


def purge_old() -> int:
    """Saqlash muddati (AUDIT_KEEP_DAYS) dan eski yozuvlarni qismlarga bo'lib o'chiradi."""
    if settings.audit_keep_days <= 0:
        return 0
    cut = datetime.now() - timedelta(days=settings.audit_keep_days)
    total = 0
    while True:
        with engine.begin() as c:
            n = c.execute(text("DELETE FROM audit WHERE created_at<:c LIMIT 5000"), {"c": cut}).rowcount
        total += n
        if n < 5000:
            return total
