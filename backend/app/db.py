from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from .config import settings

_url = make_url(settings.database_url)


def ensure_database() -> None:
    eng = create_engine(_url._replace(database=None), isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        c.execute(text(
            f"CREATE DATABASE IF NOT EXISTS `{_url.database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    eng.dispose()


engine = create_engine(_url, pool_size=10, max_overflow=10, pool_recycle=1800,
                       pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
