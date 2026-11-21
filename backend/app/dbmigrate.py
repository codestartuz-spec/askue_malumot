"""Ma'lumotlar bazasi migratsiyalari (Alembic). API va worker bir vaqtda ishga tushsa ham xavfsiz:
bitta jarayon bajaradi (MySQL GET_LOCK), qolganlari kutadi."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from .db import engine

HERE = Path(__file__).resolve().parent


def _config(conn) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(HERE / "migrations"))
    cfg.attributes["connection"] = conn
    return cfg


def upgrade(target: str = "head") -> None:
    with engine.connect() as conn:
        mysql = conn.dialect.name in ("mysql", "mariadb")
        if mysql:
            if not conn.execute(text("SELECT GET_LOCK('askue_migrate', 120)")).scalar():
                raise RuntimeError("Migratsiya qulfini olib bo'lmadi")
        try:
            command.upgrade(_config(conn), target)
            conn.commit()
        finally:
            if mysql:
                conn.execute(text("SELECT RELEASE_LOCK('askue_migrate')"))
                conn.commit()


def current() -> str | None:
    from alembic.runtime.migration import MigrationContext
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()
