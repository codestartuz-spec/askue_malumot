"""Boshlang'ich holat: jadvallar + oldingi qo'lbola migratsiyalarning (migrate.py) barcha ustun va indekslari.

Bo'sh bazada hamma jadvalni yaratadi; eski bazada faqat yetishmaganini qo'shadi (idempotent).

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

from app.migrations.helpers import add_column, add_index, drop_index
from app.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())          # faqat yo'q jadvallarni yaratadi
    for table, col in [("users", sa.Column("phone", sa.String(30), nullable=True)),
                       ("users", sa.Column("chat_id", sa.String(30), nullable=True)),
                       ("audit", sa.Column("ip", sa.String(64), nullable=True)),
                       ("trs", sa.Column("lat", sa.Float(53), nullable=True)),
                       ("trs", sa.Column("lon", sa.Float(53), nullable=True)),
                       ("tg_chats", sa.Column("members", sa.Integer, nullable=True)),
                       ("tg_chats", sa.Column("members_at", sa.DateTime, nullable=True)),
                       ("snapshots", sa.Column("out_2_7", sa.Integer, nullable=False, server_default="0")),
                       ("snapshots", sa.Column("m_direct", sa.Integer, nullable=False, server_default="0"))]:
        add_column(table, col)
    add_index("ix_m_geo2", "meters", ["lat", "lon", "ctype", "bucket", "esp_id", "brigade_id"])
    add_index("ix_m_direct", "meters", ["direct", "lat"])
    drop_index("ix_m_geo", "meters")


def downgrade() -> None:
    raise NotImplementedError("Boshlang'ich migratsiyani bekor qilib bo'lmaydi")
