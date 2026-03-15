"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2025-03-12

Создаёт все таблицы для новой БД. Для уже существующей БД
используйте: flask db stamp a1b2c3d4e5f6
"""
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    from app.extensions import db
    import app.models.all_models  # noqa: F401 — регистрирует модели в metadata
    bind = op.get_bind()
    db.metadata.create_all(bind)


def downgrade():
    # Откат начальной схемы не выполняется (полное удаление таблиц).
    pass
