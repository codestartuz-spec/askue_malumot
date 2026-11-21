"""Qurilma izi (ua_hash) va audit jurnali indekslari (qidiruv uchun).

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa

from app.migrations.helpers import add_column, add_index, drop_index

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("devices", sa.Column("ua_hash", sa.String(32), nullable=False, server_default=""))
    add_index("ix_devices_ua_hash", "devices", ["ua_hash"])
    add_index("ix_audit_created", "audit", ["created_at"])
    add_index("ix_audit_user", "audit", ["username", "id"])
    add_index("ix_audit_action", "audit", ["action", "id"])


def downgrade() -> None:
    for n, t in (("ix_audit_action", "audit"), ("ix_audit_user", "audit"), ("ix_audit_created", "audit"),
                 ("ix_devices_ua_hash", "devices")):
        drop_index(n, t)
