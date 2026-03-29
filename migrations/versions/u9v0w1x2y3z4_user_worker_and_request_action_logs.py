"""users.worker_id + request_action_logs

Revision ID: u9v0w1x2y3z4
Revises: s8t9u0v1w2x3
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from migrations.schema_util import column_exists, index_exists, table_exists

revision = "u9v0w1x2y3z4"
down_revision = "s8t9u0v1w2x3"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if not column_exists(conn, "users", "worker_id"):
        op.add_column(
            "users",
            sa.Column(
                "worker_id",
                sa.Integer(),
                sa.ForeignKey("workers.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    if not index_exists(conn, "users", "ix_users_worker_id"):
        op.create_index("ix_users_worker_id", "users", ["worker_id"], unique=False)

    if not table_exists(conn, "request_action_logs"):
        op.create_table(
            "request_action_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("request_id", sa.Integer(), sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("old_status", sa.String(length=32), nullable=True),
            sa.Column("new_status", sa.String(length=32), nullable=True),
            sa.Column("old_mode", sa.String(length=32), nullable=True),
            sa.Column("new_mode", sa.String(length=32), nullable=True),
            sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        )
    if not index_exists(conn, "request_action_logs", "ix_request_action_logs_request_id"):
        op.create_index(
            "ix_request_action_logs_request_id", "request_action_logs", ["request_id"]
        )
    if not index_exists(conn, "request_action_logs", "ix_request_action_logs_user_id"):
        op.create_index("ix_request_action_logs_user_id", "request_action_logs", ["user_id"])
    if not index_exists(conn, "request_action_logs", "ix_request_action_logs_created_at"):
        op.create_index(
            "ix_request_action_logs_created_at", "request_action_logs", ["created_at"]
        )


def downgrade():
    conn = op.get_bind()
    if index_exists(conn, "request_action_logs", "ix_request_action_logs_created_at"):
        op.drop_index("ix_request_action_logs_created_at", table_name="request_action_logs")
    if index_exists(conn, "request_action_logs", "ix_request_action_logs_user_id"):
        op.drop_index("ix_request_action_logs_user_id", table_name="request_action_logs")
    if index_exists(conn, "request_action_logs", "ix_request_action_logs_request_id"):
        op.drop_index("ix_request_action_logs_request_id", table_name="request_action_logs")
    if table_exists(conn, "request_action_logs"):
        op.drop_table("request_action_logs")

    if index_exists(conn, "users", "ix_users_worker_id"):
        op.drop_index("ix_users_worker_id", table_name="users")
    if column_exists(conn, "users", "worker_id"):
        op.drop_column("users", "worker_id")
