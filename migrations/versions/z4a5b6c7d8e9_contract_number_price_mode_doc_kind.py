"""contract document number, price mode, document kind

Revision ID: z4a5b6c7d8e9
Revises: y3z4a5b6c7d8
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa


revision = "z4a5b6c7d8e9"
down_revision = "y3z4a5b6c7d8"
branch_labels = None
depends_on = None


def _table_exists(connection, table):
    result = connection.execute(
        sa.text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_name = :t
            """
        ),
        {"t": table},
    )
    return result.scalar() is not None


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

    if _table_exists(conn, "contracts"):
        if not _column_exists(conn, "contracts", "document_number"):
            op.add_column("contracts", sa.Column("document_number", sa.String(length=128), nullable=True))
        if not _column_exists(conn, "contracts", "price_mode"):
            op.add_column(
                "contracts",
                sa.Column(
                    "price_mode",
                    sa.String(length=16),
                    nullable=False,
                    server_default="manual",
                ),
            )

    if _table_exists(conn, "contract_documents"):
        if not _column_exists(conn, "contract_documents", "document_kind"):
            op.add_column("contract_documents", sa.Column("document_kind", sa.String(length=32), nullable=True))


def downgrade():
    conn = op.get_bind()

    if _table_exists(conn, "contract_documents") and _column_exists(conn, "contract_documents", "document_kind"):
        op.drop_column("contract_documents", "document_kind")

    if _table_exists(conn, "contracts"):
        if _column_exists(conn, "contracts", "price_mode"):
            op.drop_column("contracts", "price_mode")
        if _column_exists(conn, "contracts", "document_number"):
            op.drop_column("contracts", "document_number")
