from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import log, sadmin_only
from ..models import Device, User, UserSession

router = APIRouter(prefix="/devices", tags=["devices"])
ONLINE = timedelta(minutes=5)


def _iso(d):
    return d.isoformat() if d else None


@router.get("")
def list_devices(me: User = Depends(sadmin_only), db: Session = Depends(get_db)):
    now = datetime.now()
    devs = db.scalars(select(Device).order_by(Device.last_seen.desc())).all()
    sess = db.execute(select(UserSession.device_id, UserSession.username, func.count(), func.max(UserSession.last_seen),
                             func.max(UserSession.created_at)).group_by(UserSession.device_id, UserSession.username)).all()
    by_dev: dict[int, list] = {}
    for did, un, cnt, last, first in sess:
        by_dev.setdefault(did, []).append({"username": un, "logins": cnt, "last": _iso(last)})
    active = {s.device_id: s for s in db.scalars(select(UserSession).where(UserSession.revoked.is_(False)))}
    out = []
    for d in devs:
        a = active.get(d.id)
        out.append({
            "id": d.id, "name": d.name, "kind": d.kind, "ip": d.ip, "ua": d.ua, "first_seen": _iso(d.first_seen),
            "last_seen": _iso(d.last_seen), "is_blocked": d.is_blocked, "blocked_at": _iso(d.blocked_at),
            "blocked_by": d.blocked_by, "last_user": d.last_user,
            "active_user": a.username if a else None,
            "online": bool(a and now - a.last_seen < ONLINE),
            "users": sorted(by_dev.get(d.id, []), key=lambda x: x["last"] or "", reverse=True),
        })
    return {"items": out, "total": len(out), "blocked": sum(1 for x in out if x["is_blocked"]),
            "online": sum(1 for x in out if x["online"])}


class BlockIn(BaseModel):
    blocked: bool


@router.post("/{did}/block")
def block(did: int, body: BlockIn, me: User = Depends(sadmin_only), db: Session = Depends(get_db)):
    d = db.get(Device, did)
    if not d:
        raise HTTPException(404, "Qurilma topilmadi")
    mine = db.scalar(select(UserSession).where(UserSession.device_id == did, UserSession.user_id == me.id,
                                               UserSession.revoked.is_(False)))
    if body.blocked and mine:
        raise HTTPException(400, "O'zingiz hozir foydalanayotgan qurilmani bloklab bo'lmaydi")
    d.is_blocked = body.blocked
    d.blocked_at = datetime.now() if body.blocked else None
    d.blocked_by = me.username if body.blocked else ""
    if body.blocked:   # shu qurilmadagi barcha sessiyalar to'xtatiladi
        for s in db.scalars(select(UserSession).where(UserSession.device_id == did, UserSession.revoked.is_(False))):
            s.revoked, s.reason = True, "Bu qurilma administrator tomonidan bloklangan. Administratorga murojaat qiling."
    log(db, me.username, "qurilma_blok" if body.blocked else "qurilma_ochildi", f"{d.name} • {d.ip}")
    db.commit()
    return {"ok": True}


@router.post("/{did}/logout")
def force_logout(did: int, me: User = Depends(sadmin_only), db: Session = Depends(get_db)):
    n = 0
    for s in db.scalars(select(UserSession).where(UserSession.device_id == did, UserSession.revoked.is_(False),
                                                  UserSession.user_id != me.id)):
        s.revoked, s.reason = True, "Administrator sizni tizimdan chiqardi"
        n += 1
    log(db, me.username, "qurilma_chiqarish", f"#{did} • {n} ta sessiya")
    db.commit()
    return {"ok": True, "closed": n}
