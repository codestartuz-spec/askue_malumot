import secrets

from sqlalchemy import select, text

from .config import settings
from .db import SessionLocal, engine, ensure_database, upsert_kv
from . import dbmigrate
from .models import User
from .security import hash_password


def init_db() -> None:
    ensure_database()
    dbmigrate.upgrade()      # Alembic: jadvallar va ustunlar (eski qo'lbola migrate.py o'rniga)
    _migrate_perms()
    _encrypt_token()
    with SessionLocal() as db:
        exists = db.scalar(select(User).where(User.is_super.is_(True)))
        if not exists:
            pw = settings.sadmin_password
            if not pw:       # kodda sukut bo'yicha parol yo'q: birinchi ishga tushishda tasodifiy parol yaratiladi
                pw = secrets.token_urlsafe(12)
                note = settings.data_dir / "sadmin_parol.txt"
                note.write_text(f"login: {settings.sadmin_username}\nparol: {pw}\nKirgach parolni almashtiring va bu faylni o'chiring.\n",
                                encoding="utf-8")
                print(f"SADMIN yaratildi. Login: {settings.sadmin_username}  Parol: {pw}   (fayl: {note})", flush=True)
            db.add(User(username=settings.sadmin_username, full_name="Super administrator",
                        password_hash=hash_password(pw),
                        is_super=True, is_active=True, perms=[]))
            db.commit()


def _migrate_perms() -> None:
    """Yangi ruxsatlar qo'shilganda, eski ruxsati bor xodimlarga ularni bir marta beradi."""
    from sqlalchemy import text
    from .perms import INHERIT, INHERIT_GROUPS
    with engine.begin() as c:
        done = c.execute(text("SELECT v FROM kv WHERE k='perm_migrated'")).scalar() or ""
        seen = set(done.split(",")) if done else set()
    todo = [k for k in INHERIT if k not in seen]
    todo_g = [g for g in INHERIT_GROUPS if g not in seen]
    if not todo and not todo_g:
        return
    with SessionLocal() as db:
        for u in db.scalars(select(User).where(User.is_super.is_(False))):
            cur = set(u.perms or [])
            for old in todo:
                if old in cur:
                    cur |= set(INHERIT[old])
            for g in todo_g:
                for old, new in INHERIT_GROUPS[g].items():
                    if old in cur:
                        cur |= set(new)
            if cur != set(u.perms or []):
                u.perms = sorted(cur)
        db.commit()
    with engine.begin() as c:
        upsert_kv(c, "perm_migrated", ",".join(sorted(seen | set(todo) | set(todo_g))))


def _encrypt_token() -> None:
    """Ochiq saqlangan Telegram tokenini shifrlaydi (bir marta)."""
    from .services.crypto import PREFIX, encrypt_text
    with engine.begin() as c:
        v = c.execute(text("SELECT v FROM kv WHERE k='tg_token'")).scalar()
        if v and not v.startswith(PREFIX):
            upsert_kv(c, "tg_token", encrypt_text(v))
