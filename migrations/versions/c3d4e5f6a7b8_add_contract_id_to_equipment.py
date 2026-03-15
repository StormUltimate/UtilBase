"""add contract_id to equipment

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-12

Добавляет contract_id в equipment. Для новой БД колонка уже создана
начальной миграцией — тогда шаги пропускаются.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
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
    if not _column_exists(conn, "equipment", "contract_id"):
        op.add_column("equipment", sa.Column("contract_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "equipment_contract_id_fkey", "equipment", "contracts", ["contract_id"], ["id"]
        )


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, "equipment", "contract_id"):
        op.drop_constraint("equipment_contract_id_fkey", "equipment", type_="foreignkey")
        op.drop_column("equipment", "contract_id")
