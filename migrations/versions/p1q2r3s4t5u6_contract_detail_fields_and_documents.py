"""contracts detail fields and contract documents

Revision ID: p1q2r3s4t5u6
Revises: n0p1q2r3s4t5
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa


revision = "p1q2r3s4t5u6"
down_revision = "n0p1q2r3s4t5"
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
        if not _column_exists(conn, "contracts", "created_by_user_id"):
            op.add_column("contracts", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_contracts_created_by_user_id_users",
                "contracts",
                "users",
                ["created_by_user_id"],
                ["id"],
            )
        if not _column_exists(conn, "contracts", "emergency_included_count"):
            op.add_column("contracts", sa.Column("emergency_included_count", sa.Integer(), nullable=True))
        if not _column_exists(conn, "contracts", "emergency_included_cost"):
            op.add_column("contracts", sa.Column("emergency_included_cost", sa.Numeric(12, 2), nullable=True))
        if not _column_exists(conn, "contracts", "created_at"):
            op.add_column("contracts", sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")))

    if not _table_exists(conn, "contract_documents"):
        op.create_table(
            "contract_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("file_path", sa.String(length=500), nullable=False),
            sa.Column("content_type", sa.String(length=100), nullable=True),
            sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
        )
        op.create_index("ix_contract_documents_contract_id", "contract_documents", ["contract_id"])


def downgrade():
    conn = op.get_bind()

    if _table_exists(conn, "contract_documents"):
        op.drop_index("ix_contract_documents_contract_id", table_name="contract_documents")
        op.drop_table("contract_documents")

    if _table_exists(conn, "contracts"):
        if _column_exists(conn, "contracts", "created_at"):
            op.drop_column("contracts", "created_at")
        if _column_exists(conn, "contracts", "emergency_included_cost"):
            op.drop_column("contracts", "emergency_included_cost")
        if _column_exists(conn, "contracts", "emergency_included_count"):
            op.drop_column("contracts", "emergency_included_count")
        if _column_exists(conn, "contracts", "created_by_user_id"):
            op.drop_constraint("fk_contracts_created_by_user_id_users", "contracts", type_="foreignkey")
            op.drop_column("contracts", "created_by_user_id")
