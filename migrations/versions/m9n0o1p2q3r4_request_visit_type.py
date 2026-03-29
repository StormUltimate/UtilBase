"""requests.visit_type — тип выезда (ремонт / обследование)

Revision ID: m9n0o1p2q3r4
Revises: l5m6n7o8p9q0
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'm9n0o1p2q3r4'
down_revision = 'l5m6n7o8p9q0'
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
    if not _column_exists(conn, "requests", "visit_type"):
        op.add_column(
            "requests",
            sa.Column("visit_type", sa.String(length=16), nullable=True),
        )


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, "requests", "visit_type"):
        op.drop_column("requests", "visit_type")
