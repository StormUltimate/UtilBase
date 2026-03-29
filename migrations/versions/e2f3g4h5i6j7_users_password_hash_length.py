"""users password_hash varchar 256

Revision ID: e2f3g4h5i6j7
Revises: d1e2f3g4h5i6
Create Date: 2026-03-15

Увеличивает длину users.password_hash до 256 для хешей scrypt.
"""
from alembic import op
import sqlalchemy as sa

revision = "e2f3g4h5i6j7"
down_revision = "d1e2f3g4h5i6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    length = conn.execute(
        sa.text(
            """
            SELECT character_maximum_length FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'password_hash'
            """
        )
    ).scalar()
    if length is not None and length < 256:
        op.alter_column(
            "users",
            "password_hash",
            existing_type=sa.String(length),
            type_=sa.String(256),
            existing_nullable=False,
        )


def downgrade():
    conn = op.get_bind()
    length = conn.execute(
        sa.text(
            """
            SELECT character_maximum_length FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'password_hash'
            """
        )
    ).scalar()
    if length is not None and length > 128:
        op.alter_column(
            "users",
            "password_hash",
            existing_type=sa.String(length),
            type_=sa.String(128),
            existing_nullable=False,
        )
