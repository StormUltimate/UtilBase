"""request client operations for idempotency

Revision ID: x2y3z4a5b6c7
Revises: w1x2y3z4a5b6
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa

from migrations.schema_util import index_exists, table_exists

revision = "x2y3z4a5b6c7"
down_revision = "w1x2y3z4a5b6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if not table_exists(conn, "request_client_operations"):
        op.create_table(
            "request_client_operations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("request_id", sa.Integer(), sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("operation_type", sa.String(length=32), nullable=False),
            sa.Column("client_operation_id", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint(
                "request_id",
                "user_id",
                "operation_type",
                "client_operation_id",
                name="uq_request_client_operation",
            ),
        )
    if not index_exists(conn, "request_client_operations", "ix_request_client_operations_request_id"):
        op.create_index(
            "ix_request_client_operations_request_id",
            "request_client_operations",
            ["request_id"],
        )
    if not index_exists(conn, "request_client_operations", "ix_request_client_operations_user_id"):
        op.create_index(
            "ix_request_client_operations_user_id",
            "request_client_operations",
            ["user_id"],
        )


def downgrade():
    conn = op.get_bind()
    if index_exists(conn, "request_client_operations", "ix_request_client_operations_user_id"):
        op.drop_index(
            "ix_request_client_operations_user_id", table_name="request_client_operations"
        )
    if index_exists(conn, "request_client_operations", "ix_request_client_operations_request_id"):
        op.drop_index(
            "ix_request_client_operations_request_id", table_name="request_client_operations"
        )
    if table_exists(conn, "request_client_operations"):
        op.drop_table("request_client_operations")
