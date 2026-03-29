"""clients.client_kind — вид клиента (физ/юр/комбыт/гос)

Revision ID: l5m6n7o8p9q0
Revises: j3k4l5m6n7o8
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'l5m6n7o8p9q0'
down_revision = 'j3k4l5m6n7o8'
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
    if not _column_exists(conn, "clients", "client_kind"):
        op.add_column("clients", sa.Column("client_kind", sa.String(32), nullable=True))


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, "clients", "client_kind"):
        op.drop_column("clients", "client_kind")
