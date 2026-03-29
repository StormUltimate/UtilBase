"""contracts: maintenance_wizard_json для мастера создания договора

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa


revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def _column_exists(connection, table, column):
    result = connection.execute(
        sa.text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = :t AND column_name = :c
            """
        ),
        {"t": table, "c": column},
    )
    return result.scalar() is not None


def upgrade():
    conn = op.get_bind()
    if not _column_exists(conn, "contracts", "maintenance_wizard_json"):
        op.add_column("contracts", sa.Column("maintenance_wizard_json", sa.Text(), nullable=True))


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, "contracts", "maintenance_wizard_json"):
        op.drop_column("contracts", "maintenance_wizard_json")
