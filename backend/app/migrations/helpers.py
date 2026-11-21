"""Qayta bajarilsa ham xavfsiz (idempotent) migratsiya yordamchilari: eski, qo'lda yangilangan bazalar ham ishlasin."""
import sqlalchemy as sa
from alembic import op


def _insp():
    return sa.inspect(op.get_bind())


def has_table(table: str) -> bool:
    return _insp().has_table(table)


def has_column(table: str, col: str) -> bool:
    return has_table(table) and col in {c["name"] for c in _insp().get_columns(table)}


def add_column(table: str, col: sa.Column) -> None:
    if has_table(table) and not has_column(table, col.name):
        op.add_column(table, col)


def has_index(table: str, name: str) -> bool:
    return has_table(table) and name in {i["name"] for i in _insp().get_indexes(table)}


def add_index(name: str, table: str, cols: list[str]) -> None:
    if has_table(table) and not has_index(table, name):
        op.create_index(name, table, cols)


def drop_index(name: str, table: str) -> None:
    if has_index(table, name):
        op.drop_index(name, table_name=table)
