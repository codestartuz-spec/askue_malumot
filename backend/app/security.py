from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings

ALG = "HS256"


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode()[:72], bcrypt.gensalt(rounds=11)).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode()[:72], h.encode())
    except ValueError:
        return False


def make_token(user_id: int, sid: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.token_hours)
    return jwt.encode({"sub": str(user_id), "sid": sid, "exp": exp}, settings.secret_key, algorithm=ALG)


def read_token(token: str) -> tuple[int, str] | None:
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=[ALG])
        return int(data["sub"]), str(data.get("sid") or "")
    except Exception:
        return None
