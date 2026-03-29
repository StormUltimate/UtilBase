"""workers is_active inactive_at for calendar history

Revision ID: g8h9i0j1k2l3
Revises: f7a8b9c0d1e2
Create Date: 2026-03-21

Мягкое «увольнение»: исполнитель остаётся в БД для истории заявок и календаря.
"""
from alembic import op
import sqlalchemy as sa

from migrations.schema_util import column_exists

revision = 'g8h9i0j1k2l3'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # create_all() из начальной миграции мог уже создать эти поля по текущей модели Worker.
    if not column_exists(conn, "workers", "is_active"):
        op.add_column(
            "workers",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        )
    if not column_exists(conn, "workers", "inactive_at"):
        op.add_column("workers", sa.Column("inactive_at", sa.DateTime(), nullable=True))
    op.execute(sa.text("UPDATE workers SET is_active = TRUE WHERE is_active IS NULL"))
    if column_exists(conn, "workers", "is_active"):
        op.alter_column("workers", "is_active", server_default=None)


def downgrade():
    conn = op.get_bind()
    if column_exists(conn, "workers", "inactive_at"):
        op.drop_column("workers", "inactive_at")
    if column_exists(conn, "workers", "is_active"):
        op.drop_column("workers", "is_active")
