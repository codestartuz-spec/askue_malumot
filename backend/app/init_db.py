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
    with SessionLocal() as db:
        exists = db.scalar(select(User).where(User.is_super.is_(True)))
        if not exists:
            db.add(User(username=settings.sadmin_username, full_name="Super administrator",
                        password_hash=hash_password(settings.sadmin_password),
                        is_super=True, is_active=True, perms=[]))
            db.commit()
