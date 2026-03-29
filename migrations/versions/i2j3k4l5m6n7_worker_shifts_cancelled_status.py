"""worker_shifts table + request_status.cancelled

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa

from migrations.schema_util import index_exists, table_exists

revision = "i2j3k4l5m6n7"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    op.execute(sa.text("ALTER TYPE request_status ADD VALUE IF NOT EXISTS 'cancelled'"))
    if not table_exists(conn, "worker_shifts"):
        op.create_table(
            "worker_shifts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("worker_id", sa.Integer(), nullable=False),
            sa.Column("shift_date", sa.Date(), nullable=False),
            sa.Column("time_start", sa.Time(), nullable=False),
            sa.Column("time_end", sa.Time(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["worker_id"], ["workers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("worker_id", "shift_date", name="uq_worker_shift_day"),
        )
    if not index_exists(conn, "worker_shifts", "ix_worker_shifts_worker_id"):
        op.create_index("ix_worker_shifts_worker_id", "worker_shifts", ["worker_id"], unique=False)
    if not index_exists(conn, "worker_shifts", "ix_worker_shifts_shift_date"):
        op.create_index("ix_worker_shifts_shift_date", "worker_shifts", ["shift_date"], unique=False)


def downgrade():
    conn = op.get_bind()
    if index_exists(conn, "worker_shifts", "ix_worker_shifts_shift_date"):
        op.drop_index("ix_worker_shifts_shift_date", table_name="worker_shifts")
    if index_exists(conn, "worker_shifts", "ix_worker_shifts_worker_id"):
        op.drop_index("ix_worker_shifts_worker_id", table_name="worker_shifts")
    if table_exists(conn, "worker_shifts"):
        op.drop_table("worker_shifts")
    # PostgreSQL: удалить значение из ENUM сложно — оставляем cancelled в типе
