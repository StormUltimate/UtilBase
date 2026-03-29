"""request_mode: arrived; таблица дефектов по заявке

Revision ID: y3z4a5b6c7d8
Revises: x2y3z4a5b6c7
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa

from migrations.schema_util import table_exists

revision = "y3z4a5b6c7d8"
down_revision = "x2y3z4a5b6c7"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            """
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'request_mode' AND e.enumlabel = 'arrived'
            """
        )
    ).first()
    if not row:
        conn.execute(sa.text("ALTER TYPE request_mode ADD VALUE 'arrived'"))

    if not table_exists(conn, "request_defects"):
        op.create_table(
            "request_defects",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "request_id",
                sa.Integer(),
                sa.ForeignKey("requests.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("kind", sa.String(length=16), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column(
                "media_id",
                sa.Integer(),
                sa.ForeignKey("media.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column(
                "created_by_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        )


def downgrade():
    conn = op.get_bind()
    if table_exists(conn, "request_defects"):
        op.drop_table("request_defects")
    # PostgreSQL: удалить значение из ENUM нельзя без пересоздания типа — оставляем 'arrived' в типе
