"""Qurilma aniqlash: ishonchli IP, imzolangan qurilma cookie'si, User-Agent'dan nom."""
import hashlib
import hmac
import ipaddress
import re
import secrets
from contextvars import ContextVar
from datetime import datetime
from functools import lru_cache

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Device

req_ip: ContextVar[str] = ContextVar("req_ip", default="")

BLOCKED_MSG = "Bu qurilma administrator tomonidan bloklangan. Administratorga murojaat qiling."
COOKIE = "askue_did"
COOKIE_AGE = 60 * 60 * 24 * 730


# ------------------------------------------------------------------ IP
@lru_cache(maxsize=8)
def _nets(spec: str):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if part:
            try:
                out.append(ipaddress.ip_network(part, strict=False))
            except ValueError:
                pass
    return tuple(out)


def _norm(v: str) -> str:
    v = (v or "").strip()
    try:
        return str(ipaddress.ip_address(v))
    except ValueError:
        return ""


def is_trusted(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(a in n for n in _nets(settings.trusted_proxies))


def client_ip(request: Request) -> str:
    """Haqiqiy mijoz IP si. Sarlavhalarga faqat ishonchli proksi (TRUSTED_PROXIES) yuborgan bo'lsagina ishonamiz.
    Aks holda to'g'ridan-to'g'ri ulanish manzili olinadi — begona odam sarlavhani soxtalashtira olmaydi."""
    peer = _norm(request.client.host) if request.client else ""
    if not peer or not is_trusted(peer):
        return peer[:64]
    h = request.headers
    cf = _norm(h.get("cf-connecting-ip", ""))
    if cf:
        return cf
    xff = [_norm(x) for x in h.get("x-forwarded-for", "").split(",")]
    for ip in reversed([x for x in xff if x]):      # o'ngdan chapga: birinchi ishonchsiz manzil — mijoz
        if not is_trusted(ip):
            return ip
    return (_norm(h.get("x-real-ip", "")) or (xff[0] if xff and xff[0] else "") or peer)[:64]


# ------------------------------------------------------------------ qurilma cookie
def _sig(uid: str) -> str:
    return hmac.new(settings.secret_key.encode(), f"dev|{uid}".encode(), hashlib.sha256).hexdigest()[:32]


def _read_cookie(request: Request) -> str:
    raw = request.cookies.get(COOKIE, "")
    uid, _, sig = raw.partition(".")
    if uid and sig and re.fullmatch(r"[A-Za-z0-9_-]{16,64}", uid) and hmac.compare_digest(sig, _sig(uid)):
        return uid
    return ""


def _set_cookie(request: Request, response: Response | None, uid: str) -> None:
    if response is None:
        return
    https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie(COOKIE, f"{uid}.{_sig(uid)}", max_age=COOKIE_AGE, httponly=True, samesite="lax",
                        secure=https, path="/")


def ua_hash(ua: str) -> str:
    return hashlib.sha256((ua or "").encode()).hexdigest()[:32]


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


def touch_device(db: Session, request: Request, uid: str | None = None, user: str = "",
                response: Response | None = None) -> Device:
    """Qurilmani topadi yoki yaratadi.

    Identifikator manbalari (ishonch tartibida):
      1) serverda imzolangan HttpOnly cookie — JS orqali o'g'irlab/almashtirib bo'lmaydi;
      2) eski mijozlar yuborgan localStorage UUID (birinchi uchrashuvda cookie'ga o'tkaziladi);
      3) hech biri yo'q (cookie va storage tozalangan) — oldin bloklangan qurilma bilan IP+UA mos kelsa,
         o'sha bloklangan qurilma deb olinadi, aks holda yangi qurilma yaratiladi.
    """
    ip = client_ip(request)
    ua = request.headers.get("user-agent", "")[:400]
    h = ua_hash(ua)
    sid = _read_cookie(request)
    legacy = re.sub(r"[^A-Za-z0-9_-]", "", (uid or ""))[:64]
    d: Device | None = None
    if sid:
        d = db.scalar(select(Device).where(Device.uid == sid))
    if d is None and len(legacy) >= 16:
        d = db.scalar(select(Device).where(Device.uid == legacy))
    if d is None and not sid:
        # belgilarsiz qaytgan: bloklangan qurilmaning "izi" (IP + UA) bilan solishtirish
        d = db.scalar(select(Device).where(Device.is_blocked.is_(True), Device.ua_hash == h, Device.ip == ip))
    name, kind = parse_ua(ua)
    if d is None:
        d = Device(uid=sid or secrets.token_hex(16), name=name, kind=kind, ua=ua, ip=ip, ua_hash=h)
        db.add(d)
        db.flush()
    d.ip, d.ua, d.ua_hash, d.name, d.kind, d.last_seen = ip, ua, h, name, kind, datetime.now()
    if user:
        d.last_user = user
    _set_cookie(request, response, d.uid)
    return d
