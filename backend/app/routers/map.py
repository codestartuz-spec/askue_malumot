from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import need
from ..metrics import METER_SPEC, TR_SPEC
from ..models import User

router = APIRouter(prefix="/map", tags=["map"])

POINT_LIMIT = 2500
CTYPE_KIND = {"aholi": 2, "ulgurji": 1, "balans": 3}
# Hisoblagich holatlari (har biri alohida): bucket 1..5 = 0-2 kun, 2-7, 7-30, 1-3 oy, 3 oydan ortiq; 0 = umuman obxod yo'q
METER_STATE = {"m1": "m.bucket=1", "m2": "m.bucket=2", "m3": "m.bucket=3", "m4": "m.bucket=4", "m5": "m.bucket=5",
               "m0": "m.bucket=0", "mdir": "m.direct=1"}
# Konsentrator holatlari: online / offline / 3 kundan ortiq offline / holati noma'lum / biriktirilmagan, obxod darajalari
TR_STATE = {"t1": "t.state=1", "t2": "(t.state=2 AND t.offline3=0)", "t3": "t.offline3=1", "t0": "t.state=0",
            "tun": "(t.has_dcu=1 AND t.attached=0)",
            "l1": "t.lv=1", "l2": "t.lv=2", "l3": "t.lv=3", "l4": "t.lv=4", "l5": "t.lv=5"}


def _filters(esp_id, brigade_id, s, w, n, e, alias: str, geo: str = "") -> tuple[list[str], dict]:
    conds = [f"{alias}.lat IS NOT NULL"]
    p: dict = {}
    if esp_id:
        conds.append(f"{alias}.esp_id=:esp")
        p["esp"] = esp_id
    if brigade_id is not None:
        if brigade_id == 0:
            conds.append(f"{alias}.brigade_id IS NULL")
        else:
            conds.append(f"{alias}.brigade_id=:brig")
            p["brig"] = brigade_id
    if None not in (s, w, n, e):
        conds.append(f"{alias}.lat BETWEEN :s AND :n AND {alias}.lon BETWEEN :w AND :e")
        p.update(s=s, n=n, w=w, e=e)
    return conds, p


def _meter_where(kinds, status, metric, esp_id, brigade_id, bbox):
    conds, p = _filters(esp_id, brigade_id, *bbox, alias="m")
    cts = [CTYPE_KIND[k] for k in kinds if k in CTYPE_KIND]
    if not cts:
        return None, p
    conds.append(f"m.ctype IN ({','.join(str(c) for c in cts)})")
    ms = [METER_STATE[x] for x in status if x in METER_STATE]
    if ms:
        conds.append("(" + " OR ".join(ms) + ")")
    if metric in METER_SPEC:
        conds.append(f"({METER_SPEC[metric]})")
    return " AND ".join(conds), p


def _tr_where(status, metric, esp_id, brigade_id, bbox):
    conds, p = _filters(esp_id, brigade_id, *bbox, alias="t")
    ts = [TR_STATE[x] for x in status if x in TR_STATE]
    if ts:
        conds.append("(" + " OR ".join(ts) + ")")
    if metric in TR_SPEC:
        conds.append(f"({TR_SPEC[metric]})")
    return " AND ".join(conds), p


def _csv(v: str | None) -> list[str]:
    return [x for x in (v or "").split(",") if x]


@router.get("/points")
def points(kinds: str = "aholi,ulgurji,balans,tr", status: str = "", metric: str = "",
           esp_id: int | None = None, brigade_id: int | None = None,
           s: float | None = None, w: float | None = None, n: float | None = None, e: float | None = None,
           zoom: float = 10, _: User = Depends(need("map.view")), db: Session = Depends(get_db)):
    ks, sts = _csv(kinds), _csv(status)
    bbox = (s, w, n, e)
    has_m = any(x in METER_STATE for x in sts)
    has_t = any(x in TR_STATE for x in sts)
    want_m = metric not in TR_SPEC and any(k in CTYPE_KIND for k in ks) and (has_m or not sts)
    want_t = metric not in METER_SPEC and "tr" in ks and (has_t or not sts)
    mw, mp = _meter_where(ks, sts, metric, esp_id, brigade_id, bbox) if want_m else (None, {})
    tw, tp = _tr_where(sts, metric, esp_id, brigade_id, bbox) if want_t else (None, {})
    n_m = db.execute(text(f"SELECT COUNT(*) FROM meters m WHERE {mw}"), mp).scalar() if mw else 0
    n_t = db.execute(text(f"SELECT COUNT(*) FROM trs t WHERE {tw}"), tp).scalar() if tw else 0
    out = {"meters": n_m, "trs": n_t, "points": [], "clusters": []}

    if n_m + n_t <= POINT_LIMIT:
        out["mode"] = "points"
        if mw:
            for r in db.execute(text(
                    "SELECT m.meter_no, m.account, m.name, m.address, m.tp_no, m.ctype, m.mtype, m.link, "
                    "m.bucket, m.direct, m.days, m.last_poll, m.lat, m.lon, e.label AS esp, b.name AS brig "
                    "FROM meters m JOIN esps e ON e.id=m.esp_id LEFT JOIN brigades b ON b.id=m.brigade_id "
                    f"WHERE {mw}"), mp).mappings():
                out["points"].append({
                    "t": "m", "id": r["meter_no"], "la": r["lat"], "lo": r["lon"], "ct": r["ctype"], "b": r["bucket"], "dr": bool(r["direct"]),
                    "acc": r["account"], "name": r["name"], "addr": r["address"], "tp": r["tp_no"],
                    "mt": r["mtype"], "ln": r["link"], "days": r["days"], "esp": r["esp"], "brig": r["brig"],
                    "last": r["last_poll"].strftime("%Y-%m-%d %H:%M") if r["last_poll"] else None})
        if tw:
            for r in db.execute(text(
                    "SELECT t.id, t.tp_no, t.dcu, t.substation, t.feeder, t.state, t.obx_level, t.lv, t.lat, t.lon, "
                    "t.attached, t.offline3, e.label AS esp, b.name AS brig, "
                    "(SELECT COUNT(*) FROM meters m WHERE m.tr_id=t.id) AS mc, "
                    "(SELECT COUNT(*) FROM meters m WHERE m.tr_id=t.id AND m.bucket>=3) AS mout "
                    "FROM trs t JOIN esps e ON e.id=t.esp_id LEFT JOIN brigades b ON b.id=t.brigade_id "
                    f"WHERE {tw}"), tp).mappings():
                out["points"].append({
                    "t": "t", "id": r["id"], "la": r["lat"], "lo": r["lon"], "tp": r["tp_no"], "dcu": r["dcu"],
                    "sub": r["substation"], "feeder": r["feeder"], "st": r["state"], "obx": r["obx_level"],
                    "lv": r["lv"], "off3": bool(r["offline3"]), "att": bool(r["attached"]), "esp": r["esp"],
                    "brig": r["brig"], "mc": r["mc"], "mout": r["mout"]})
        return out

    # Ko'p nuqta: tarmoq (grid) bo'yicha jamlash
    out["mode"] = "clusters"
    step = 360.0 / (2 ** max(int(zoom), 1)) * 0.34
    singles_m, singles_t = [], []
    if mw:
        for r in db.execute(text(
                f"SELECT FLOOR(m.lat/{step}) gy, FLOOR(m.lon/{step}) gx, COUNT(*) c, AVG(m.lat) la, AVG(m.lon) lo, "
                f"SUM(m.bucket>=3) bad, SUM(m.bucket=0) nn, MIN(m.meter_no) k FROM meters m WHERE {mw} "
                "GROUP BY gy, gx"), mp).mappings():
            if r["c"] == 1:
                singles_m.append(r["k"])
            else:
                out["clusters"].append({"t": "m", "n": int(r["c"]), "la": r["la"], "lo": r["lo"],
                                        "bad": int(r["bad"] or 0), "nn": int(r["nn"] or 0)})
    if tw:
        for r in db.execute(text(
                f"SELECT FLOOR(t.lat/{step}) gy, FLOOR(t.lon/{step}) gx, COUNT(*) c, AVG(t.lat) la, AVG(t.lon) lo, "
                f"SUM(t.state=2) bad, MIN(t.id) k FROM trs t WHERE {tw} GROUP BY gy, gx"), tp).mappings():
            if r["c"] == 1:
                singles_t.append(r["k"])
            else:
                out["clusters"].append({"t": "t", "n": int(r["c"]), "la": r["la"], "lo": r["lo"],
                                        "bad": int(r["bad"] or 0), "nn": 0})
    from sqlalchemy import bindparam
    if singles_m:
        singles_m = singles_m[:1500]
        for r in db.execute(text(
                "SELECT m.meter_no, m.account, m.name, m.address, m.tp_no, m.ctype, m.mtype, m.link, m.bucket, "
                "m.days, m.direct, m.last_poll, m.lat, m.lon, e.label AS esp, b.name AS brig FROM meters m "
                "JOIN esps e ON e.id=m.esp_id LEFT JOIN brigades b ON b.id=m.brigade_id "
                "WHERE m.meter_no IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": singles_m}).mappings():
            out["points"].append({
                "t": "m", "id": r["meter_no"], "la": r["lat"], "lo": r["lon"], "ct": r["ctype"], "b": r["bucket"], "dr": bool(r["direct"]),
                "acc": r["account"], "name": r["name"], "addr": r["address"], "tp": r["tp_no"], "mt": r["mtype"],
                "ln": r["link"], "days": r["days"], "esp": r["esp"], "brig": r["brig"],
                "last": r["last_poll"].strftime("%Y-%m-%d %H:%M") if r["last_poll"] else None})
    if singles_t:
        for r in db.execute(text(
                "SELECT t.id, t.tp_no, t.dcu, t.substation, t.feeder, t.state, t.obx_level, t.lv, t.lat, t.lon, "
                "t.attached, t.offline3, e.label AS esp, b.name AS brig, "
                "(SELECT COUNT(*) FROM meters m WHERE m.tr_id=t.id) AS mc, "
                "(SELECT COUNT(*) FROM meters m WHERE m.tr_id=t.id AND m.bucket>=3) AS mout "
                "FROM trs t JOIN esps e ON e.id=t.esp_id LEFT JOIN brigades b ON b.id=t.brigade_id "
                "WHERE t.id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": singles_t[:1500]}).mappings():
            out["points"].append({
                "t": "t", "id": r["id"], "la": r["lat"], "lo": r["lon"], "tp": r["tp_no"], "dcu": r["dcu"],
                "sub": r["substation"], "feeder": r["feeder"], "st": r["state"], "obx": r["obx_level"], "lv": r["lv"],
                "off3": bool(r["offline3"]), "att": bool(r["attached"]), "esp": r["esp"], "brig": r["brig"],
                "mc": r["mc"], "mout": r["mout"]})
    return out


@router.get("/find")
def find(q: str, _: User = Depends(need("map.view")), db: Session = Depends(get_db)):
    """Hisoblagich raqami / hisob raqam / TP bo'yicha qidirish."""
    q = q.strip()
    res = []
    if not q:
        return res
    if q.isdigit():
        for r in db.execute(text(
                "SELECT meter_no, account, name, address, lat, lon FROM meters "
                "WHERE (meter_no LIKE :q OR account LIKE :q) LIMIT 8"), {"q": f"{q}%"}).mappings():
            res.append({"t": "m", "id": r["meter_no"], "title": f"{r['meter_no']} — {r['name']}",
                        "sub": r["address"], "la": r["lat"], "lo": r["lon"]})
    else:
        for r in db.execute(text(
                "SELECT meter_no, account, name, address, lat, lon FROM meters "
                "WHERE name LIKE :q LIMIT 8"), {"q": f"%{q}%"}).mappings():
            res.append({"t": "m", "id": r["meter_no"], "title": f"{r['meter_no']} — {r['name']}",
                        "sub": r["address"], "la": r["lat"], "lo": r["lon"]})
    for r in db.execute(text(
            "SELECT t.id, t.tp_no, t.dcu, t.lat, t.lon, e.label FROM trs t JOIN esps e ON e.id=t.esp_id "
            "WHERE t.tp_no LIKE :q OR t.dcu LIKE :q LIMIT 6"), {"q": f"{q}%"}).mappings():
        res.append({"t": "t", "id": r["id"], "title": f"TP {r['tp_no']} — {r['label']}",
                    "sub": f"DCU {r['dcu'] or '—'}", "la": r["lat"], "lo": r["lon"]})
    return res


@router.get("/counts")
def counts(esp_id: int | None = None, brigade_id: int | None = None,
           _: User = Depends(need("map.view")), db: Session = Depends(get_db)):
    """Har bir holat bo'yicha koordinatasi bor qurilmalar soni (filtr tugmalarida ko'rsatish uchun)."""
    mc, mp = _filters(esp_id, brigade_id, None, None, None, None, alias="m")
    tc, tp = _filters(esp_id, brigade_id, None, None, None, None, alias="t")
    msel = ", ".join(f"COALESCE(SUM({c}),0) AS {k}" for k, c in METER_STATE.items())
    tsel = ", ".join(f"COALESCE(SUM({c}),0) AS {k}" for k, c in TR_STATE.items())
    out = {k: int(v or 0) for k, v in db.execute(text(f"SELECT {msel} FROM meters m WHERE {' AND '.join(mc)}"), mp).mappings().first().items()}
    out |= {k: int(v or 0) for k, v in db.execute(text(f"SELECT {tsel} FROM trs t WHERE {' AND '.join(tc)}"), tp).mappings().first().items()}
    return out


@router.get("/stats")
def stats(esp_id: int | None = None, brigade_id: int | None = None,
          _: User = Depends(need("map.view")), db: Session = Depends(get_db)):
    p: dict = {}
    cm, ct = "1=1", "1=1"
    if esp_id:
        cm += " AND esp_id=:e"
        ct += " AND esp_id=:e"
        p["e"] = esp_id
    if brigade_id is not None:
        cond = " AND brigade_id IS NULL" if brigade_id == 0 else " AND brigade_id=:b"
        cm += cond
        ct += cond
        if brigade_id:
            p["b"] = brigade_id
    m = db.execute(text(f"SELECT COUNT(*) t, SUM(lat IS NOT NULL) g FROM meters WHERE {cm}"), p).first()
    t = db.execute(text(f"SELECT COUNT(*) t, SUM(lat IS NOT NULL) g FROM trs WHERE {ct}"), p).first()
    bb = db.execute(text(f"SELECT MIN(lat), MAX(lat), MIN(lon), MAX(lon) FROM trs WHERE lat IS NOT NULL AND {ct}"), p).first()
    if not bb or bb[0] is None:
        bb = db.execute(text(f"SELECT MIN(lat), MAX(lat), MIN(lon), MAX(lon) FROM meters WHERE lat BETWEEN 37 AND 40.5 "
                             f"AND lon BETWEEN 63 AND 69 AND {cm}"), p).first()
    bounds = [[float(bb[0]), float(bb[2])], [float(bb[1]), float(bb[3])]] if bb and bb[0] is not None else None
    return {"meters": int(m[0] or 0), "meters_geo": int(m[1] or 0), "trs": int(t[0] or 0), "trs_geo": int(t[1] or 0),
            "bounds": bounds}
