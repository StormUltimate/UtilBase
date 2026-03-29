"""pending/overdue -> assigned; авто-просрочка отключена в коде

Revision ID: a3b4c5d6e7f8
Revises: z4a5b6c7d8e9
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a3b4c5d6e7f8"
down_revision = "z4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "UPDATE requests SET status = 'assigned' WHERE status IN ('pending', 'overdue')"
        )
    )


def downgrade():
    pass
