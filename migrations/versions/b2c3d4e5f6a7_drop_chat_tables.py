"""drop chat tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-03-12

Удаление таблиц чата: chat_rooms, messages, chatroom_users
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('messages', if_exists=True)
    op.drop_table('chatroom_users', if_exists=True)
    op.drop_table('chat_rooms', if_exists=True)


def downgrade():
    op.create_table(
        'chat_rooms',
        op.Column('id', sa.Integer(), nullable=False),
        op.Column('name', sa.String(100), nullable=True),
        op.Column('is_group', sa.Boolean(), nullable=False, server_default='false'),
        op.Column('created_at', sa.DateTime(), nullable=True),
        op.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'chatroom_users',
        op.Column('chatroom_id', sa.Integer(), nullable=False),
        op.Column('user_id', sa.Integer(), nullable=False),
        op.ForeignKeyConstraint(['chatroom_id'], ['chat_rooms.id']),
        op.ForeignKeyConstraint(['user_id'], ['users.id']),
        op.PrimaryKeyConstraint('chatroom_id', 'user_id')
    )
    op.create_table(
        'messages',
        op.Column('id', sa.Integer(), nullable=False),
        op.Column('chat_room_id', sa.Integer(), nullable=False),
        op.Column('sender_id', sa.Integer(), nullable=False),
        op.Column('content', sa.Text(), nullable=True),
        op.Column('media_id', sa.Integer(), nullable=True),
        op.Column('type', sa.Enum('text', 'image', 'video', 'file', name='message_type'), nullable=False),
        op.Column('timestamp', sa.DateTime(), nullable=False),
        op.Column('read_by', postgresql.JSONB(), nullable=True),
        op.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        op.ForeignKeyConstraint(['chat_room_id'], ['chat_rooms.id']),
        op.ForeignKeyConstraint(['sender_id'], ['users.id']),
        op.ForeignKeyConstraint(['media_id'], ['media.id'], ondelete='SET NULL'),
        op.PrimaryKeyConstraint('id')
    )
