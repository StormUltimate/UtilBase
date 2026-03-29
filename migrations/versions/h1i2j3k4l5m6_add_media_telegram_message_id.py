"""media.telegram_message_id for caption neighbor search

Revision ID: h1i2j3k4l5m6
Revises: g8h9i0j1k2l3
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa

from migrations.schema_util import column_exists, index_exists

revision = "h1i2j3k4l5m6"
down_revision = "g8h9i0j1k2l3"
branch_labels = None
depends_on = None

IX_MEDIA_CHAT_TELEGRAM = "ix_media_chat_telegram_message_id"


def upgrade():
    conn = op.get_bind()
    if not column_exists(conn, "media", "telegram_message_id"):
        op.add_column("media", sa.Column("telegram_message_id", sa.BigInteger(), nullable=True))
    if not index_exists(conn, "media", IX_MEDIA_CHAT_TELEGRAM):
        op.create_index(
            IX_MEDIA_CHAT_TELEGRAM,
            "media",
            ["chat_id", "telegram_message_id"],
            unique=False,
        )


def downgrade():
    conn = op.get_bind()
    if index_exists(conn, "media", IX_MEDIA_CHAT_TELEGRAM):
        op.drop_index(IX_MEDIA_CHAT_TELEGRAM, table_name="media")
    if column_exists(conn, "media", "telegram_message_id"):
        op.drop_column("media", "telegram_message_id")
