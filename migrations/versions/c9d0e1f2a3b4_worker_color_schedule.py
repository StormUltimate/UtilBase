"""worker color for schedule timeline

Revision ID: c9d0e1f2a3b4
Revises: b4c5d6e7f8a9
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a3b4"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workers",
        sa.Column("color", sa.String(length=32), nullable=True),
    )


def downgrade():
    op.drop_column("workers", "color")
