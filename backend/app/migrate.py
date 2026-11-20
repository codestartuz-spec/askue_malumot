"""Mavjud bazani yangi versiyaga o'tkazish: yetishmayotgan ustun va indekslarni qo'shadi."""
from sqlalchemy import text

from .db import engine

COLUMNS = [
    ("users", "phone", "VARCHAR(30) NULL"),
    ("users", "chat_id", "VARCHAR(30) NULL"),
    ("trs", "lat", "DOUBLE NULL"),
    ("trs", "lon", "DOUBLE NULL"),
    ("tg_chats", "members", "INT NULL"),
    ("tg_chats", "members_at", "DATETIME NULL"),
    ("snapshots", "out_2_7", "INT NOT NULL DEFAULT 0"),
    ("snapshots", "m_direct", "INT NOT NULL DEFAULT 0"),
]
INDEXES = [("meters", "ix_m_geo2", "lat, lon, ctype, bucket, esp_id, brigade_id"),
           ("meters", "ix_m_direct", "direct, lat")]
DROP_INDEXES = [("meters", "ix_m_geo")]


def ensure_schema() -> None:
    with engine.begin() as c:
        db = c.execute(text("SELECT DATABASE()")).scalar()
        for table, col, ddl in COLUMNS:
            has = c.execute(text("SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=:d "
                                 "AND TABLE_NAME=:t AND COLUMN_NAME=:c"), {"d": db, "t": table, "c": col}).first()
            if not has:
                c.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
        for table, name, cols in INDEXES:
            has = c.execute(text("SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=:d "
                                 "AND TABLE_NAME=:t AND INDEX_NAME=:i"), {"d": db, "t": table, "i": name}).first()
            if not has:
                c.execute(text(f"CREATE INDEX {name} ON {table} ({cols})"))
        for table, name in DROP_INDEXES:
            has = c.execute(text("SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=:d "
                                 "AND TABLE_NAME=:t AND INDEX_NAME=:i"), {"d": db, "t": table, "i": name}).first()
            if has:
                c.execute(text(f"DROP INDEX {name} ON {table}"))
