import time

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError

from .config import settings
from .db import SessionLocal, engine, ensure_database
from .migrate import ensure_schema
from .models import Base, User
from .security import hash_password


def init_db() -> None:
    ensure_database()
    for attempt in range(5):
        try:
            Base.metadata.create_all(engine)
            break
        except (OperationalError, ProgrammingError):   # API va worker bir vaqtda ishga tushganda
            time.sleep(1 + attempt)
    ensure_schema()
    _migrate_perms()
    with SessionLocal() as db:
        exists = db.scalar(select(User).where(User.is_super.is_(True)))
        if not exists:
            db.add(User(username=settings.sadmin_username, full_name="Super administrator",
                        password_hash=hash_password(settings.sadmin_password),
                        is_super=True, is_active=True, perms=[]))
            db.commit()


def _migrate_perms() -> None:
    """Yangi ruxsatlar qo'shilganda, eski ruxsati bor xodimlarga ularni bir marta beradi."""
    from sqlalchemy import text
    from .perms import INHERIT
    with engine.begin() as c:
        done = c.execute(text("SELECT v FROM kv WHERE k='perm_migrated'")).scalar() or ""
        seen = set(done.split(",")) if done else set()
    todo = [k for k in INHERIT if k not in seen]
    if not todo:
        return
    with SessionLocal() as db:
        for u in db.scalars(select(User).where(User.is_super.is_(False))):
            cur = set(u.perms or [])
            for old in todo:
                if old in cur:
                    cur |= set(INHERIT[old])
            if cur != set(u.perms or []):
                u.perms = sorted(cur)
        db.commit()
    with engine.begin() as c:
        c.execute(text("REPLACE INTO kv (k,v) VALUES ('perm_migrated',:v)"), {"v": ",".join(sorted(seen | set(todo)))})
