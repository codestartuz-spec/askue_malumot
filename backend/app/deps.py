from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from datetime import datetime, timedelta

from .models import Audit, Device, User, UserSession
from .security import read_token
from .services.devices import BLOCKED_MSG, client_ip, req_ip


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else request.query_params.get("token", "")
    tk = read_token(token) if token else None
    if not tk:
        raise HTTPException(401, "Tizimga qayta kiring")
    uid, sid = tk
    ss = db.scalar(select(UserSession).where(UserSession.sid == sid)) if sid else None
    if not ss or ss.user_id != uid:
        raise HTTPException(401, "Tizimga qayta kiring")
    dev = db.get(Device, ss.device_id)
    if dev and dev.is_blocked:
        raise HTTPException(401, BLOCKED_MSG)
    if ss.revoked:
        raise HTTPException(401, ss.reason or "Tizimga qayta kiring")
    user = db.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(401, "Foydalanuvchi faol emas")
    now = datetime.now()
    if now - ss.last_seen > timedelta(seconds=60):   # har so'rovda yozmaslik uchun
        ss.last_seen = now
        ss.ip = client_ip(request)
        if dev:
            dev.last_seen, dev.ip = now, ss.ip
        db.commit()
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
    db.add(Audit(username=username, action=action, detail=detail[:4000], ip=req_ip.get() or None))
