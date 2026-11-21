from sqlalchemy import create_engine, event, text
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


# MySQL 8 sukut bo'yicha qat'iy sql_mode bilan ishlaydi (ONLY_FULL_GROUP_BY...). MariaDB'da esa bunday emas —
# shuning uchun har ulanishda bir xil rejim o'rnatiladi: ikkala bazada ham xatti-harakat bir xil bo'ladi.
MYSQL8_MODE = ("ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,"
               "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION")

engine = create_engine(_url, pool_size=10, max_overflow=10, pool_recycle=1800, pool_pre_ping=True)


if settings.sql_mode_strict:
    @event.listens_for(engine, "connect")
    def _set_mode(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute(f"SET SESSION sql_mode='{MYSQL8_MODE}'")
        cur.close()
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def upsert_kv(conn, k: str, v: str) -> None:
    """kv jadvaliga yozish/yangilash (MySQL 8 va MariaDB uchun bir xil)."""
    from sqlalchemy.dialects.mysql import insert
    from .models import Kv
    st = insert(Kv).values(k=k, v=v)
    conn.execute(st.on_duplicate_key_update(v=st.inserted.v))


def insert_id(conn, sql: str, params: dict | None = None) -> int:
    """INSERT bajaradi va yangi qator ID sini qaytaradi (LAST_INSERT_ID() o'rniga — ulanishga bog'liq emas)."""
    return int(conn.execute(text(sql), params or {}).lastrowid)
