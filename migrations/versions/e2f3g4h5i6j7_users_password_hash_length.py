"""users password_hash varchar 256

Revision ID: e2f3g4h5i6j7
Revises: d1e2f3g4h5i6
Create Date: 2026-03-15

Увеличивает длину users.password_hash до 256 для хешей scrypt.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e2f3g4h5i6j7'
down_revision = 'd1e2f3g4h5i6'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'users',
        'password_hash',
        existing_type=sa.String(128),
        type_=sa.String(256),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        'users',
        'password_hash',
        existing_type=sa.String(256),
        type_=sa.String(128),
        existing_nullable=False,
    )
