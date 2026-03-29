"""add contract_scope_uid to requests

Revision ID: q6r7s8t9u0v1
Revises: p1q2r3s4t5u6
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa


revision = "q6r7s8t9u0v1"
down_revision = "p1q2r3s4t5u6"
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


def _index_exists(connection, table, index_name):
    result = connection.execute(
        sa.text(
            """
            SELECT 1 FROM pg_indexes
            WHERE tablename = :t AND indexname = :i
            """
        ),
        {"t": table, "i": index_name},
    )
    return result.scalar() is not None


def upgrade():
    conn = op.get_bind()

    if not _column_exists(conn, "requests", "contract_scope_uid"):
        op.add_column("requests", sa.Column("contract_scope_uid", sa.String(length=64), nullable=True))

    if not _index_exists(conn, "requests", "uq_requests_contract_scope_uid"):
        op.create_index(
            "uq_requests_contract_scope_uid",
            "requests",
            ["contract_scope_uid"],
            unique=True,
            postgresql_where=sa.text("contract_scope_uid IS NOT NULL"),
        )


def downgrade():
    conn = op.get_bind()

    if _index_exists(conn, "requests", "uq_requests_contract_scope_uid"):
        op.drop_index("uq_requests_contract_scope_uid", table_name="requests")

    if _column_exists(conn, "requests", "contract_scope_uid"):
        op.drop_column("requests", "contract_scope_uid")
