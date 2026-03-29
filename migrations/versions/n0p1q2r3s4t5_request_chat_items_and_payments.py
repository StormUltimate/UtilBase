"""request chat + order items + request payments

Revision ID: n0p1q2r3s4t5
Revises: m9n0o1p2q3r4
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa


revision = "n0p1q2r3s4t5"
down_revision = "m9n0o1p2q3r4"
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

    if not _table_exists(conn, "chat_threads"):
        op.create_table(
            "chat_threads",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("request_id", sa.Integer(), sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
        )
        op.create_index("ix_chat_threads_request_id", "chat_threads", ["request_id"])

    if not _table_exists(conn, "chat_participants"):
        op.create_table(
            "chat_participants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("thread_id", sa.Integer(), sa.ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("last_read_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
            sa.UniqueConstraint("thread_id", "user_id", name="uq_chat_thread_user"),
        )
        op.create_index("ix_chat_participants_thread_id", "chat_participants", ["thread_id"])
        op.create_index("ix_chat_participants_user_id", "chat_participants", ["user_id"])

    if not _table_exists(conn, "chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("thread_id", sa.Integer(), sa.ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("message_text", sa.Text(), nullable=False),
            sa.Column("is_edited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"])
        op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])

    if not _table_exists(conn, "request_items"):
        op.create_table(
            "request_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("request_id", sa.Integer(), sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_type", sa.String(length=16), nullable=False, server_default="material"),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
            sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("line_total", sa.Numeric(12, 2), nullable=True),
            sa.Column("source", sa.String(length=32), nullable=True),  # client_ordered / master_recommended / other
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
        )
        op.create_index("ix_request_items_request_id", "request_items", ["request_id"])

    if not _table_exists(conn, "request_payments"):
        op.create_table(
            "request_payments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("request_id", sa.Integer(), sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("payment_method", sa.String(length=32), nullable=True),  # cash / online / transfer
            sa.Column("is_cash", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("received_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
        )
        op.create_index("ix_request_payments_request_id", "request_payments", ["request_id"])
        op.create_index("ix_request_payments_client_id", "request_payments", ["client_id"])

    # Дополнительно: связь старой таблицы payments с заявкой (необязательно, но удобно для отчётов переходного периода).
    if _table_exists(conn, "payments") and not _column_exists(conn, "payments", "request_id"):
        op.add_column("payments", sa.Column("request_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_payments_request_id_requests",
            "payments",
            "requests",
            ["request_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_payments_request_id", "payments", ["request_id"])


def downgrade():
    conn = op.get_bind()

    if _table_exists(conn, "payments") and _column_exists(conn, "payments", "request_id"):
        op.drop_index("ix_payments_request_id", table_name="payments")
        op.drop_constraint("fk_payments_request_id_requests", "payments", type_="foreignkey")
        op.drop_column("payments", "request_id")

    if _table_exists(conn, "request_payments"):
        op.drop_index("ix_request_payments_client_id", table_name="request_payments")
        op.drop_index("ix_request_payments_request_id", table_name="request_payments")
        op.drop_table("request_payments")

    if _table_exists(conn, "request_items"):
        op.drop_index("ix_request_items_request_id", table_name="request_items")
        op.drop_table("request_items")

    if _table_exists(conn, "chat_messages"):
        op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
        op.drop_index("ix_chat_messages_thread_id", table_name="chat_messages")
        op.drop_table("chat_messages")

    if _table_exists(conn, "chat_participants"):
        op.drop_index("ix_chat_participants_user_id", table_name="chat_participants")
        op.drop_index("ix_chat_participants_thread_id", table_name="chat_participants")
        op.drop_table("chat_participants")

    if _table_exists(conn, "chat_threads"):
        op.drop_index("ix_chat_threads_request_id", table_name="chat_threads")
        op.drop_table("chat_threads")
