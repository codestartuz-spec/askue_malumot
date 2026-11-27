"""Respublika dinamikasi (barcha viloyatlar): nation_reports jadvali.

Revision ID: 0004
Revises: 0003
"""
from alembic import op

from app.migrations.helpers import has_table
from app.models import NationReport

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not has_table(NationReport.__tablename__):
        NationReport.__table__.create(op.get_bind())


def downgrade() -> None:
    if has_table("nation_reports"):
        op.drop_table("nation_reports")
