"""telegram_chats and telegram_messages for Telegram bot

Revision ID: f7a8b9c0d1e2
Revises: e2f3g4h5i6j7
Create Date: 2026-03-21

Таблицы для управления чатами бота и хранения сообщений из Telegram.
"""
from alembic import op
import sqlalchemy as sa

revision = 'f7a8b9c0d1e2'
down_revision = 'e2f3g4h5i6j7'
branch_labels = None
depends_on = None

IX_TELEGRAM_MESSAGES_CHAT_ID = "ix_telegram_messages_chat_id"


def _table_exists(connection, table):
    result = connection.execute(
        sa.text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :t
            """
        ),
        {"t": table},
    )
    return result.scalar() is not None


def _index_exists(connection, table, index_name):
    result = connection.execute(
        sa.text(
            """
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = :t AND indexname = :i
            """
        ),
        {"t": table, "i": index_name},
    )
    return result.scalar() is not None


def upgrade():
    conn = op.get_bind()

    # Начальная миграция (create_all по моделям) могла уже создать эти таблицы.
    if not _table_exists(conn, "telegram_chats"):
        op.create_table(
            "telegram_chats",
            sa.Column("chat_id", sa.String(length=50), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("download_enabled", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("chat_id"),
        )
    if not _table_exists(conn, "telegram_messages"):
        op.create_table(
            "telegram_messages",
            sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
            sa.Column("sender", sa.String(length=255), nullable=True),
            sa.Column("message_text", sa.Text(), nullable=True),
            sa.Column("message_date", sa.DateTime(), nullable=True),
            sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
            sa.Column("chat_id", sa.String(length=50), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("telegram_message_id", "chat_id", name="uq_telegram_message_id_chat"),
        )
    if not _index_exists(conn, "telegram_messages", IX_TELEGRAM_MESSAGES_CHAT_ID):
        op.create_index(
            IX_TELEGRAM_MESSAGES_CHAT_ID,
            "telegram_messages",
            ["chat_id"],
            unique=False,
        )


def downgrade():
    conn = op.get_bind()
    if _index_exists(conn, "telegram_messages", IX_TELEGRAM_MESSAGES_CHAT_ID):
        op.drop_index(IX_TELEGRAM_MESSAGES_CHAT_ID, table_name="telegram_messages")
    if _table_exists(conn, "telegram_messages"):
        op.drop_table("telegram_messages")
    if _table_exists(conn, "telegram_chats"):
        op.drop_table("telegram_chats")
