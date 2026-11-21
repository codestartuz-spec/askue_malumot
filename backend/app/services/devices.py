"""Qurilma aniqlash: User-Agent'dan nom, IP manzil, qurilma yozuvi."""
import re
from contextvars import ContextVar
from datetime import datetime

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Device

req_ip: ContextVar[str] = ContextVar("req_ip", default="")

BLOCKED_MSG = "Bu qurilma administrator tomonidan bloklangan. Administratorga murojaat qiling."


def client_ip(request: Request) -> str:
    h = request.headers
    ip = h.get("cf-connecting-ip") or (h.get("x-forwarded-for", "").split(",")[0].strip()) or h.get("x-real-ip") \
        or (request.client.host if request.client else "")
    return ip[:64]


def parse_ua(ua: str) -> tuple[str, str]:
    """(nom, tur): masalan ('Chrome • Windows 10/11', 'desktop')."""
    u = ua or ""
    if "Edg/" in u: br = "Edge"
    elif "OPR/" in u or "Opera" in u: br = "Opera"
    elif "YaBrowser" in u: br = "Yandex"
    elif "SamsungBrowser" in u: br = "Samsung Internet"
    elif "Firefox/" in u: br = "Firefox"
    elif "Chrome/" in u or "CriOS" in u: br = "Chrome"
    elif "Safari/" in u: br = "Safari"
    else: br = "Brauzer"
    if "Android" in u:
        mm = re.search(r"Android [\d.]+; ([^;)]+)", u)
        os_, kind = "Android" + (f" ({mm.group(1).strip()})" if mm else ""), "mobile"
    elif "iPhone" in u: os_, kind = "iPhone (iOS)", "mobile"
    elif "iPad" in u: os_, kind = "iPad (iOS)", "tablet"
    elif "Windows NT 10" in u: os_, kind = "Windows 10/11", "desktop"
    elif "Windows" in u: os_, kind = "Windows", "desktop"
    elif "Mac OS X" in u: os_, kind = "macOS", "desktop"
    elif "CrOS" in u: os_, kind = "ChromeOS", "desktop"
    elif "Linux" in u: os_, kind = "Linux", "desktop"
    else: os_, kind = "Noma'lum tizim", "desktop"
    return f"{br} • {os_}"[:120], kind


def touch_device(db: Session, request: Request, uid: str | None, user: str = "") -> Device:
    """Qurilmani topadi yoki yaratadi; IP va oxirgi faollikni yangilaydi."""
    uid = re.sub(r"[^A-Za-z0-9_-]", "", (uid or ""))[:64]
    ip = client_ip(request)
    ua = request.headers.get("user-agent", "")[:400]
    if len(uid) < 16:   # ID kelmasa — IP + UA asosida
        import hashlib
        uid = "x" + hashlib.sha1(f"{ip}|{ua}".encode()).hexdigest()[:30]
    d = db.scalar(select(Device).where(Device.uid == uid))
    name, kind = parse_ua(ua)
    if not d:
        d = Device(uid=uid, name=name, kind=kind, ua=ua, ip=ip)
        db.add(d)
        db.flush()
    d.ip, d.ua, d.name, d.kind, d.last_seen = ip, ua, name, kind, datetime.now()
    if user:
        d.last_user = user
    return d
