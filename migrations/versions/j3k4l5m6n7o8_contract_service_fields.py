"""contract fields: counterparty kind, conclusion, periodicity, equipment list

Revision ID: j3k4l5m6n7o8
Revises: i2j3k4l5m6n7
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'j3k4l5m6n7o8'
down_revision = 'i2j3k4l5m6n7'
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
    cols = [
        ("counterparty_kind", sa.String(32), True),
        ("conclusion_date", sa.Date(), True),
        ("term_note", sa.Text(), True),
        ("service_periodicity", sa.Text(), True),
        ("equipment_scope", sa.Text(), True),
    ]
    for name, coltype, nullable in cols:
        if not _column_exists(conn, "contracts", name):
            op.add_column("contracts", sa.Column(name, coltype, nullable=nullable))


def downgrade():
    conn = op.get_bind()
    for name in (
        "equipment_scope",
        "service_periodicity",
        "term_note",
        "conclusion_date",
        "counterparty_kind",
    ):
        if _column_exists(conn, "contracts", name):
            op.drop_column("contracts", name)
