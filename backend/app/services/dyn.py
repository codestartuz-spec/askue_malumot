from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..metrics import ALL_METRICS
from ..models import snapshots


def _d(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def compute(db: Session, esp_id, date_from, date_to, can_cmp: bool = True) -> dict:
    dates = [r[0] for r in db.execute(select(snapshots.c.snap_date).distinct()
                                      .order_by(snapshots.c.snap_date.desc()))]
    if not dates:
        return {"dates": [], "to": None, "base": None, "esp": None, "rows": [], "total": None}

    to = _d(date_to) if can_cmp else None
    if to not in dates:
        to = dates[0]
    base = _d(date_from) if can_cmp else None
    if base not in dates or base >= to:
        month = [d for d in dates if d.year == to.year and d.month == to.month and d < to]
        base = min(month) if month else None
        if base is None:
            earlier = [d for d in dates if d < to]
            base = max(earlier) if earlier else None

    key = snapshots.c.brigade_id if esp_id else snapshots.c.esp_id
    q = (select(snapshots.c.snap_date, key.label("k"),
                *[func.sum(snapshots.c[m]).label(m) for m in ALL_METRICS])
         .where(snapshots.c.snap_date.in_([d for d in (to, base) if d]))
         .group_by(snapshots.c.snap_date, key))
    if esp_id:
        q = q.where(snapshots.c.esp_id == esp_id)
    cur_map, base_map = {}, {}
    for r in db.execute(q).mappings():
        vals = {m: int(r[m] or 0) for m in ALL_METRICS}
        (cur_map if r["snap_date"] == to else base_map)[r["k"]] = vals

    names = {}
    if esp_id:
        for b in db.execute(text("SELECT id, name, number FROM brigades WHERE esp_id=:e"), {"e": esp_id}):
            names[b[0]] = (b[1], b[2])
        names[0] = ("Biriktirilmagan", 10_000)
        keys = sorted(cur_map.keys() | base_map.keys(), key=lambda k: names.get(k, ("", 99_999))[1])
        label = lambda k: names.get(k, ("O'chirilgan brigada", 0))[0]   # noqa: E731
        esp = db.execute(text("SELECT id, label FROM esps WHERE id=:e"), {"e": esp_id}).mappings().first()
    else:
        order = {}
        for e in db.execute(text("SELECT id, label, sort FROM esps")):
            names[e[0]] = e[1]
            order[e[0]] = (e[2], e[1])
        keys = sorted(cur_map.keys() | base_map.keys(), key=lambda k: order.get(k, (999, "")))
        label = lambda k: names.get(k, str(k))   # noqa: E731
        esp = None

    zero = {m: 0 for m in ALL_METRICS}
    staff: dict[int, list[str]] = {}
    if esp_id:
        for b, nm in db.execute(text("SELECT bm.brigade_id, bm.full_name FROM brigade_members bm "
                                     "JOIN brigades b ON b.id=bm.brigade_id WHERE b.esp_id=:e ORDER BY bm.sort, bm.id"),
                                {"e": esp_id}):
            staff.setdefault(b, []).append(nm)
    rows = [{"id": k, "name": label(k), "members": staff.get(k, []), "cur": cur_map.get(k, zero),
             "base": base_map.get(k, zero) if base else None} for k in keys]
    tot = lambda mp: {m: sum(v[m] for v in mp.values()) for m in ALL_METRICS}   # noqa: E731
    return {"dates": [d.isoformat() for d in dates], "to": to.isoformat(),
            "base": base.isoformat() if base else None,
            "esp": dict(esp) if esp else None, "rows": rows,
            "total": {"cur": tot(cur_map), "base": tot(base_map) if base else None}}
