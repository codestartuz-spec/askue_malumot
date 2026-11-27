"""PDF yuklash vazifalari: pdf_jobs jadvali.

Revision ID: 0005
Revises: 0004
"""
from alembic import op

from app.migrations.helpers import has_table
from app.models import PdfJob

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not has_table(PdfJob.__tablename__):
        PdfJob.__table__.create(op.get_bind())


def downgrade() -> None:
    if has_table("pdf_jobs"):
        op.drop_table("pdf_jobs")
