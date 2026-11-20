from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import log, sadmin_only
from ..models import User
from ..perms import NEEDS, PERM_CODES
from ..security import hash_password
from .auth import clean_contact, user_out

router = APIRouter(prefix="/users", tags=["users"])


class UserIn(BaseModel):
    username: str
    full_name: str = ""
    password: str
    perms: list[str] = []
    phone: str | None = None
    chat_id: str | None = None


class UserPatch(BaseModel):
    full_name: str | None = None
    perms: list[str] | None = None
    is_active: bool | None = None
    password: str | None = None
    phone: str | None = None
    chat_id: str | None = None


def _clean(perms: list[str]) -> list[str]:
    ok = {p for p in perms if p in PERM_CODES}
    ok |= {NEEDS[p] for p in ok if p in NEEDS}      # bog'liq ruxsatni avtomatik qo'shadi
    return sorted(ok)


@router.get("")
def list_users(_: User = Depends(sadmin_only), db: Session = Depends(get_db)):
    return [user_out(u) for u in db.scalars(select(User).order_by(User.is_super.desc(), User.id))]


@router.post("")
def create_user(body: UserIn, me: User = Depends(sadmin_only), db: Session = Depends(get_db)):
    name = body.username.strip().lower()
    if len(name) < 3 or not name.replace("_", "").replace(".", "").isalnum():
        raise HTTPException(400, "Login kamida 3 ta harf/raqamdan iborat bo'lsin")
    if len(body.password) < 6:
        raise HTTPException(400, "Parol kamida 6 belgidan iborat bo'lsin")
    if db.scalar(select(User).where(User.username == name)):
        raise HTTPException(400, "Bunday login mavjud")
    ph, cid = clean_contact(db, body.phone, body.chat_id, None)
    u = User(username=name, full_name=body.full_name.strip(), password_hash=hash_password(body.password),
             perms=_clean(body.perms), phone=ph, chat_id=cid)
    db.add(u)
    log(db, me.username, "xodim_qo'shildi", f"{name}: {u.perms}")
    db.commit()
    return user_out(u)


@router.patch("/{uid}")
def patch_user(uid: int, body: UserPatch, me: User = Depends(sadmin_only), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Topilmadi")
    if u.is_super and (body.perms is not None or body.is_active is False):
        raise HTTPException(400, "Sadmin ruxsatlarini o'zgartirib bo'lmaydi")
    changes = []
    if body.full_name is not None:
        u.full_name = body.full_name.strip()
    if body.perms is not None:
        old = set(u.perms or [])
        u.perms = _clean(body.perms)
        changes.append(f"ruxsatlar: +{sorted(set(u.perms) - old)} -{sorted(old - set(u.perms))}")
    if body.is_active is not None and body.is_active != u.is_active:
        u.is_active = body.is_active
        changes.append("faol" if u.is_active else "bloklandi")
    if body.phone is not None or body.chat_id is not None:
        ph, cid = clean_contact(db, body.phone if body.phone is not None else u.phone,
                                body.chat_id if body.chat_id is not None else u.chat_id, u.id)
        if (ph, cid) != (u.phone, u.chat_id):
            u.phone, u.chat_id = ph, cid
            changes.append("telefon / chat ID")
    if body.password:
        if len(body.password) < 6:
            raise HTTPException(400, "Parol kamida 6 belgidan iborat bo'lsin")
        u.password_hash = hash_password(body.password)
        changes.append("parol almashtirildi")
    log(db, me.username, "xodim_o'zgardi", f"{u.username}: {'; '.join(changes) or 'ism'}")
    db.commit()
    return user_out(u)


@router.delete("/{uid}")
def delete_user(uid: int, me: User = Depends(sadmin_only), db: Session = Depends(get_db)):
    """Xodimni butunlay o'chiradi (qaytarib bo'lmaydi). Harakatlar jurnalidagi yozuvlar login nomi bilan qoladi."""
    from sqlalchemy import text
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Topilmadi")
    if u.is_super:
        raise HTTPException(400, "Sadminni o'chirib bo'lmaydi")
    if u.id == me.id:
        raise HTTPException(400, "O'zingizni o'chira olmaysiz")
    name = u.username
    try:
        db.execute(text("DELETE FROM pw_resets WHERE user_id=:i"), {"i": uid})
    except Exception:  # noqa: BLE001
        db.rollback()
        u = db.get(User, uid)
    db.delete(u)
    log(db, me.username, "xodim_ochirildi", name)
    db.commit()
    return {"ok": True}
