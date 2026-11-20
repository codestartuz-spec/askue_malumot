"""Bosh sahifa: so'nggi statistika (kunlik snapshotlar va respublika PDF'lari bo'yicha)."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import need, need_any
from ..metrics import ALL_METRICS
from ..models import RepublicReport, User, snapshots

router = APIRouter(prefix="/home", tags=["home"])
DAYS = 30


@router.get("/daily")
def daily(_: User = Depends(need_any("view.konsentrator", "view.aloqa", "view.obxod")), db: Session = Depends(get_db)):
    cols = [func.sum(snapshots.c[m]).label(m) for m in ALL_METRICS]
    rows = db.execute(select(snapshots.c.snap_date, *cols).group_by(snapshots.c.snap_date)
                      .order_by(snapshots.c.snap_date.desc()).limit(DAYS)).mappings().all()
    if not rows:
        return {"dates": [], "series": {}, "latest": None, "prev": None, "districts": []}
    rows = list(reversed(rows))
    dates = [r["snap_date"] for r in rows]
    series = {m: [int(r[m] or 0) for r in rows] for m in ALL_METRICS}
    latest, prev = dates[-1], (dates[-2] if len(dates) > 1 else None)
    order = {r[0]: (r[2], r[1]) for r in db.execute(text("SELECT id, label, sort FROM esps"))}
    dist = {}
    for d in (latest, prev):
        if not d:
            continue
        q = select(snapshots.c.esp_id, *cols).where(snapshots.c.snap_date == d).group_by(snapshots.c.esp_id)
        for r in db.execute(q).mappings():
            e = dist.setdefault(r["esp_id"], {"id": r["esp_id"], "name": order.get(r["esp_id"], ("", "?"))[1],
                                              "cur": {}, "base": {}})
            e["cur" if d == latest else "base"] = {m: int(r[m] or 0) for m in ALL_METRICS}
    ds = sorted(dist.values(), key=lambda x: order.get(x["id"], (999, ""))[0])
    last = {m: series[m][-1] for m in ALL_METRICS}
    pv = {m: series[m][-2] for m in ALL_METRICS} if prev else None
    return {"dates": [d.isoformat() for d in dates], "series": series, "latest": last, "prev": pv,
            "districts": ds, "to": latest.isoformat(), "from": prev.isoformat() if prev else None}


@router.get("/republic")
def republic(_: User = Depends(need("republic.view")), db: Session = Depends(get_db)):
    reps = list(db.scalars(select(RepublicReport).order_by(RepublicReport.end_date.desc()).limit(DAYS)))
    out = []
    for i, r in enumerate(reversed(reps)):
        latest = r is reps[0]
        pages = []
        for p in r.data.get("pages", []):
            pg = {"n": p["n"], "title": p.get("title", ""),
                  "cells": [{"label": c.get("label", ""), "v": c.get("v"), "p": c.get("p"), "d": c.get("d")}
                            for c in p["cells"]]}
            if latest:
                pg["rows"] = [{"name": x["name"], "cells": [{"v": c.get("v"), "p": c.get("p"), "d": c.get("d")}
                                                          for c in x["cells"]]} for x in p.get("rows", [])]
            pages.append(pg)
        out.append({"end": r.end_date.isoformat(), "start": r.start_date.isoformat() if r.start_date else None,
                    "pages": pages})
    return {"reports": out}
