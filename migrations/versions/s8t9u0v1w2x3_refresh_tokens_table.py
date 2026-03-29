"""refresh_tokens for JWT refresh revocation

Revision ID: s8t9u0v1w2x3
Revises: q6r7s8t9u0v1
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa

from migrations.schema_util import index_exists, table_exists

revision = "s8t9u0v1w2x3"
down_revision = "q6r7s8t9u0v1"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if not table_exists(conn, "refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("jti", sa.String(length=64), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        )
    if not index_exists(conn, "refresh_tokens", "ix_refresh_tokens_user_id"):
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    if not index_exists(conn, "refresh_tokens", "ix_refresh_tokens_jti"):
        op.create_index("ix_refresh_tokens_jti", "refresh_tokens", ["jti"], unique=True)


def downgrade():
    conn = op.get_bind()
    if index_exists(conn, "refresh_tokens", "ix_refresh_tokens_jti"):
        op.drop_index("ix_refresh_tokens_jti", table_name="refresh_tokens")
    if index_exists(conn, "refresh_tokens", "ix_refresh_tokens_user_id"):
        op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    if table_exists(conn, "refresh_tokens"):
        op.drop_table("refresh_tokens")
