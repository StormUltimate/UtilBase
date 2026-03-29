"""legacy placeholder: демо-данные больше не создаются при миграции

Revision ID: d1e2f3g4h5i6
Revises: c3d4e5f6a7b8
Create Date: 2026-03-13

Ранее эта ревизия вставляла демо-исполнителей и заявки при каждом `flask db upgrade`.
Демо-клиенты, заявки, оборудование и т.п. создаются только через панель администрирования
или `/demo` → `create_demo_data()` в `app/utils/demo_db.py`.

Ревизию оставляем в цепочке Alembic с тем же revision id.
"""

from alembic import op
import sqlalchemy as sa


revision = "d1e2f3g4h5i6"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    # Намеренно пусто: не засоряем прод и чистые БД демо-заявками.
    pass


def downgrade():
    bind = op.get_bind()

    demo_requests = bind.execute(
        sa.text("SELECT id FROM requests WHERE description LIKE 'DEMO:%'")
    ).fetchall()
    demo_ids = [row[0] for row in demo_requests]

    if demo_ids:
        bind.execute(
            sa.text("DELETE FROM request_workers WHERE request_id = ANY(:ids)"),
            {"ids": demo_ids},
        )
        bind.execute(
            sa.text("DELETE FROM requests WHERE id = ANY(:ids)"),
            {"ids": demo_ids},
        )

    bind.execute(sa.text("DELETE FROM workers WHERE full_name LIKE 'Демо %'"))
