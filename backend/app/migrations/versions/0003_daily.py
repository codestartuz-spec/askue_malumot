"""Kunlik topshiriq bo'limi: daily_batches jadvali.

Revision ID: 0003
Revises: 0002
"""
from alembic import op

from app.migrations.helpers import has_table
from app.models import DailyBatch, DailySetting

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for model in (DailyBatch, DailySetting):
        if not has_table(model.__tablename__):
            model.__table__.create(op.get_bind())


def downgrade() -> None:
    for t in ("daily_settings", "daily_batches"):
        if has_table(t):
            op.drop_table(t)
