import hashlib
import re
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, log
from ..config import settings
from ..models import PwReset, User
from ..services import telegram as tg
from ..perms import PERM_CODES
from ..security import (clear_fails, hash_password, make_token, register_fail, too_many_attempts,
                        verify_password)

router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(u: User) -> dict:
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "is_super": u.is_super,
            "is_active": u.is_active, "phone": u.phone or "", "chat_id": u.chat_id or "", "perms": sorted(PERM_CODES) if u.is_super else (u.perms or []),
            "last_login": u.last_login.isoformat() if u.last_login else None}


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = f"{request.client.host if request.client else '?'}|{body.username.lower()}"
    if too_many_attempts(key):
        raise HTTPException(429, "Urinishlar ko'p. Bir necha daqiqadan keyin qayta urinib ko'ring")
    u = db.scalar(select(User).where(User.username == body.username.strip()))
    if not u or not u.is_active or not verify_password(body.password, u.password_hash):
        register_fail(key)
        raise HTTPException(401, "Login yoki parol noto'g'ri")
    clear_fails(key)
    u.last_login = datetime.now()
    db.commit()
    return {"token": make_token(u.id), "user": user_out(u)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


class PwIn(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password")
def change_password(body: PwIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "Joriy parol noto'g'ri")
    if len(body.new_password) < 6:
        raise HTTPException(400, "Yangi parol kamida 6 belgidan iborat bo'lsin")
    user.password_hash = hash_password(body.new_password)
    log(db, user.username, "parol", "Parol almashtirildi")
    db.commit()
    return {"ok": True}


# ----------------------------------------------------------------- profil
def clean_contact(db: Session, phone: str | None, chat_id: str | None, uid: int | None):
    """Telefon va chat ID'ni tekshiradi. Qaytadi: (phone|None, chat_id|None)."""
    ph = re.sub(r"[^\d+]", "", phone or "")[:30] or None
    if ph and len(re.sub(r"\D", "", ph)) < 9:
        raise HTTPException(400, "Telefon raqami noto'g'ri (masalan: +998901234567)")
    cid = (chat_id or "").strip() or None
    if cid:
        if not re.fullmatch(r"-?\d{5,15}", cid):
            raise HTTPException(400, "Telegram chat ID faqat raqamlardan iborat bo'lishi kerak")
        dup = db.scalar(select(User).where(User.chat_id == cid, User.id != (uid or 0)))
        if dup:
            raise HTTPException(400, f"Bu chat ID boshqa xodimga («{dup.username}») biriktirilgan")
    return ph, cid


class ProfileIn(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    chat_id: str | None = None


@router.patch("/profile")
def update_profile(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ph, cid = clean_contact(db, body.phone, body.chat_id, user.id)
    user.phone, user.chat_id = ph, cid
    if body.full_name is not None:
        user.full_name = body.full_name.strip()[:150]
    log(db, user.username, "profil", "Telefon / Telegram chat ID yangilandi")
    db.commit()
    return user_out(user)


# ------------------------------------------------- parolni Telegram orqali tiklash
def _hash_code(code: str, uid: int) -> str:
    return hashlib.sha256(f"{settings.secret_key}|{uid}|{code}".encode()).hexdigest()


class ForgotIn(BaseModel):
    username: str


@router.post("/forgot")
def forgot(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    key = f"forgot|{request.client.host if request.client else '?'}"
    if too_many_attempts(key):
        raise HTTPException(429, "Urinishlar ko'p. Bir necha daqiqadan keyin qayta urinib ko'ring")
    register_fail(key)
    u = db.scalar(select(User).where(User.username == body.username.strip().lower()))
    if not u or not u.is_active:
        raise HTTPException(404, "Bunday login topilmadi")
    if not u.chat_id:
        raise HTTPException(400, "Bu xodimga Telegram chat ID kiritilmagan. Sadmin'ga murojaat qiling")
    last = db.scalar(select(PwReset).where(PwReset.user_id == u.id).order_by(PwReset.id.desc()))
    if last and datetime.now() - last.created_at < timedelta(seconds=45):
        raise HTTPException(429, "Kod yaqinda yuborilgan. Bir daqiqa kuting")
    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        tg.send_text(u.chat_id, f"🔐 ASKUE ma'lumot — parolni tiklash kodi: {code}\n"
                                "Kod 10 daqiqa amal qiladi. Siz so'ramagan bo'lsangiz, e'tibor bermang.")
    except tg.TgError as e:
        raise HTTPException(502, f"Kodni yuborib bo'lmadi: {e}. Botga /start bosganingizni tekshiring") from e
    db.query(PwReset).filter(PwReset.user_id == u.id).delete()
    db.add(PwReset(user_id=u.id, code_hash=_hash_code(code, u.id), expires=datetime.now() + timedelta(minutes=10)))
    db.commit()
    return {"ok": True}


class ResetIn(BaseModel):
    username: str
    code: str
    new_password: str


@router.post("/reset")
def reset(body: ResetIn, db: Session = Depends(get_db)):
    if len(body.new_password) < 6:
        raise HTTPException(400, "Yangi parol kamida 6 belgidan iborat bo'lsin")
    u = db.scalar(select(User).where(User.username == body.username.strip().lower()))
    r = db.scalar(select(PwReset).where(PwReset.user_id == u.id).order_by(PwReset.id.desc())) if u else None
    if not u or not r or r.expires < datetime.now() or r.tries >= 5:
        raise HTTPException(400, "Kod eskirgan yoki noto'g'ri. Yangi kod so'rang")
    if not secrets.compare_digest(r.code_hash, _hash_code(body.code.strip(), u.id)):
        r.tries += 1
        db.commit()
        raise HTTPException(400, "Kod noto'g'ri")
    u.password_hash = hash_password(body.new_password)
    db.delete(r)
    log(db, u.username, "parol_tiklash", "Parol Telegram kodi orqali tiklandi")
    db.commit()
    return {"ok": True}
