from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import Audit, User
from .security import read_token


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else request.query_params.get("token", "")
    uid = read_token(token) if token else None
    if not uid:
        raise HTTPException(401, "Tizimga qayta kiring")
    user = db.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(401, "Foydalanuvchi faol emas")
    return user


def has_perm(user: User, code: str) -> bool:
    return user.is_super or code in (user.perms or [])


def need(code: str):
    def dep(user: User = Depends(current_user)) -> User:
        if not has_perm(user, code):
            raise HTTPException(403, "Bu amal uchun ruxsat yo'q")
        return user
    return dep


def need_any(*codes: str):
    def dep(user: User = Depends(current_user)) -> User:
        if not any(has_perm(user, c) for c in codes):
            raise HTTPException(403, "Bu amal uchun ruxsat yo'q")
        return user
    return dep


def sadmin_only(user: User = Depends(current_user)) -> User:
    if not user.is_super:
        raise HTTPException(403, "Faqat sadmin uchun")
    return user


def log(db: Session, username: str, action: str, detail: str = "") -> None:
    db.add(Audit(username=username, action=action, detail=detail[:4000]))
