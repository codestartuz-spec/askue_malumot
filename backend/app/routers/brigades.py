from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import log, need
from ..models import Brigade, BrigadeMember, User
from ..services import snapshots

router = APIRouter(prefix="/brigades", tags=["brigades"])


class Member(BaseModel):
    full_name: str
    position: str | None = None


class BrigadePatch(BaseModel):
    name: str | None = None
    members: list[Member] | None = None


class BrigadeNew(BaseModel):
    esp_id: int
    name: str
    members: list[Member] = []


class AssignIn(BaseModel):
    esp_id: int
    brigade_id: int                         # 0 = biriktirishni olib tashlash
    tr_ids: list[int] | None = None
    from_brigade_id: int | None = None      # tr_ids o'rniga: shu brigadaning (0 = biriktirilmagan) barcha TP'lari
    use_from: bool = False


def _members(db: Session, brigade_ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    if not brigade_ids:
        return out
    rows = db.execute(text(
        "SELECT brigade_id, full_name, position FROM brigade_members "
        "WHERE brigade_id IN :ids ORDER BY brigade_id, sort, id").bindparams(
        __import__("sqlalchemy").bindparam("ids", expanding=True)), {"ids": brigade_ids})
    for r in rows:
        out.setdefault(r[0], []).append({"full_name": r[1], "position": r[2]})
    return out


@router.get("")
def list_brigades(esp_id: int | None = None, _: User = Depends(need("brigade.view")), db: Session = Depends(get_db)):
    """esp_id berilmasa — barcha tumanlarning barcha brigadalari."""
    cond = "WHERE b.esp_id=:e" if esp_id else ""
    p = {"e": esp_id} if esp_id else {}
    bs = db.execute(text("SELECT b.id, b.esp_id, e.label AS esp, b.name, b.number, b.source_name, b.updated_at "
                         f"FROM brigades b JOIN esps e ON e.id=b.esp_id {cond} ORDER BY e.sort, e.label, b.number"),
                    p).mappings().all()
    w = "WHERE esp_id=:e" if esp_id else ""
    tr_cnt = {(r[0], r[1]): r[2] for r in db.execute(text(
        f"SELECT esp_id, COALESCE(brigade_id,0), COUNT(*) FROM trs {w} GROUP BY 1,2"), p)}
    m_cnt = {(r[0], r[1]): r[2] for r in db.execute(text(
        f"SELECT esp_id, COALESCE(brigade_id,0), COUNT(*) FROM meters {w} GROUP BY 1,2"), p)}
    mem = _members(db, [b["id"] for b in bs])
    items = [{"id": b["id"], "esp_id": b["esp_id"], "esp": b["esp"], "name": b["name"], "number": b["number"],
              "source_name": b["source_name"],
              "updated_at": b["updated_at"].isoformat() if b["updated_at"] else None,
              "members": mem.get(b["id"], []), "tp_count": tr_cnt.get((b["esp_id"], b["id"]), 0),
              "meter_count": m_cnt.get((b["esp_id"], b["id"]), 0)} for b in bs]
    unassigned = []
    for e in db.execute(text(f"SELECT id, label FROM esps {'WHERE id=:e' if esp_id else ''} ORDER BY sort, label"), p):
        c = tr_cnt.get((e[0], 0), 0)
        if c:
            unassigned.append({"esp_id": e[0], "esp": e[1], "tp_count": c, "meter_count": m_cnt.get((e[0], 0), 0)})
    return {"items": items, "unassigned": unassigned}


def _set_members(db: Session, brigade_id: int, members: list[Member]) -> None:
    db.execute(text("DELETE FROM brigade_members WHERE brigade_id=:b"), {"b": brigade_id})
    for i, m in enumerate(members):
        nm = m.full_name.strip()
        if nm:
            db.add(BrigadeMember(brigade_id=brigade_id, full_name=nm[:150], sort=i,
                                 position=(m.position or "").strip()[:100] or None))


@router.patch("/{bid}")
def patch_brigade(bid: int, body: BrigadePatch, user: User = Depends(need("brigade.edit")),
                  db: Session = Depends(get_db)):
    b = db.get(Brigade, bid)
    if not b:
        raise HTTPException(404, "Brigada topilmadi")
    old_members = [r[0] for r in db.execute(text(
        "SELECT full_name FROM brigade_members WHERE brigade_id=:b ORDER BY sort"), {"b": bid})]
    changes = []
    if body.name is not None and body.name.strip() and body.name.strip() != b.name:
        changes.append(f"nom: «{b.name}» → «{body.name.strip()}»")
        b.name = body.name.strip()[:120]
    if body.members is not None:
        _set_members(db, bid, body.members)
        new = [m.full_name.strip() for m in body.members if m.full_name.strip()]
        if new != old_members:
            changes.append(f"xodimlar: {old_members} → {new}")
    if changes:
        log(db, user.username, "brigada_tahrir", f"#{bid}: " + "; ".join(changes))
    db.commit()
    return {"ok": True}


@router.post("")
def create_brigade(body: BrigadeNew, user: User = Depends(need("brigade.edit")),
                   db: Session = Depends(get_db)):
    n = (db.execute(text("SELECT COALESCE(MAX(number),0) FROM brigades WHERE esp_id=:e"),
                    {"e": body.esp_id}).scalar() or 0) + 1
    b = Brigade(esp_id=body.esp_id, manager_key=f"QO'LDA-{n}-{__import__('uuid').uuid4().hex[:8]}",
                number=n, name=body.name.strip() or f"{n}-brigada", source_name="")
    db.add(b)
    db.flush()
    _set_members(db, b.id, body.members)
    log(db, user.username, "brigada_qo'shildi", f"#{b.id} {b.name}")
    db.commit()
    return {"id": b.id}


@router.post("/assign")
def assign(body: AssignIn, user: User = Depends(need("brigade.assign")), db: Session = Depends(get_db)):
    if body.brigade_id:
        ok = db.execute(text("SELECT 1 FROM brigades WHERE id=:b AND esp_id=:e"),
                        {"b": body.brigade_id, "e": body.esp_id}).first()
        if not ok:
            raise HTTPException(400, "Brigada bu tumanga tegishli emas")
    if body.use_from:
        cond = "brigade_id IS NULL" if not body.from_brigade_id else "brigade_id=:f"
        ids = [r[0] for r in db.execute(text(f"SELECT id FROM trs WHERE esp_id=:e AND {cond}"),
                                        {"e": body.esp_id, "f": body.from_brigade_id})]
    else:
        ids = body.tr_ids or []
    if not ids:
        return {"moved": 0}
    target = body.brigade_id or None
    moved = 0
    for i in range(0, len(ids), 1000):
        chunk = ids[i:i + 1000]
        ph = ",".join(str(int(x)) for x in chunk)
        moved += db.execute(text(
            f"UPDATE trs SET brigade_id=:b, manual=1 WHERE esp_id=:e AND id IN ({ph})"),
            {"b": target, "e": body.esp_id}).rowcount
        db.execute(text(f"UPDATE meters SET brigade_id=:b WHERE esp_id=:e AND tr_id IN ({ph})"),
                   {"b": target, "e": body.esp_id})
    latest = db.execute(text("SELECT MAX(snap_date) FROM snapshots")).scalar()
    if latest:
        snapshots.write(db.connection(), latest, body.esp_id)   # joriy kesim darhol yangilansin
    name = db.execute(text("SELECT name FROM brigades WHERE id=:b"), {"b": body.brigade_id}).scalar() \
        if body.brigade_id else "Biriktirilmagan"
    log(db, user.username, "tp_biriktirish", f"{moved} ta TP → «{name}» (tuman #{body.esp_id})")
    db.commit()
    return {"moved": moved}


@router.get("/trs")
def brigade_trs(esp_id: int, brigade_id: int = 0, q: str = "", page: int = 1, size: int = 50,
                _: User = Depends(need("brigade.view")), db: Session = Depends(get_db)):
    """Brigadaga (0 = biriktirilmagan) tegishli TP'lar ro'yxati — biriktirish oynasi uchun."""
    size = max(10, min(size, 200))
    params: dict = {"e": esp_id, "l": size, "o": (max(page, 1) - 1) * size}
    cond = "esp_id=:e AND " + ("brigade_id IS NULL" if brigade_id == 0 else "brigade_id=:b")
    if brigade_id:
        params["b"] = brigade_id
    if q.strip():
        cond += " AND (tp_no LIKE :q OR dcu LIKE :q OR substation LIKE :q OR feeder LIKE :q)"
        params["q"] = f"%{q.strip()}%"
    total = db.execute(text(f"SELECT COUNT(*) FROM trs WHERE {cond}"), params).scalar() or 0
    rows = db.execute(text(f"SELECT id, tp_no, substation, feeder, dcu, manual FROM trs WHERE {cond} "
                           "ORDER BY id LIMIT :l OFFSET :o"), params).mappings()
    return {"total": total, "items": [dict(r) for r in rows]}
