"""checklist templates and request answers

Revision ID: v0w1x2y3z4a5
Revises: u9v0w1x2y3z4
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa

from migrations.schema_util import index_exists, table_exists

revision = "v0w1x2y3z4a5"
down_revision = "u9v0w1x2y3z4"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    if not table_exists(conn, "checklist_templates"):
        op.create_table(
            "checklist_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("equipment_type", sa.String(length=100), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
    if not index_exists(conn, "checklist_templates", "ix_checklist_templates_equipment_type"):
        op.create_index(
            "ix_checklist_templates_equipment_type", "checklist_templates", ["equipment_type"]
        )

    if not table_exists(conn, "checklist_template_items"):
        op.create_table(
            "checklist_template_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "template_id",
                sa.Integer(),
                sa.ForeignKey("checklist_templates.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("item_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("item_type", sa.String(length=32), nullable=False, server_default="boolean"),
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
        )
    if not index_exists(conn, "checklist_template_items", "ix_checklist_template_items_template_id"):
        op.create_index(
            "ix_checklist_template_items_template_id",
            "checklist_template_items",
            ["template_id"],
        )

    if not table_exists(conn, "request_checklist_answers"):
        op.create_table(
            "request_checklist_answers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("request_id", sa.Integer(), sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "template_item_id",
                sa.Integer(),
                sa.ForeignKey("checklist_template_items.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("checked", sa.Boolean(), nullable=True),
            sa.Column("value_text", sa.Text(), nullable=True),
            sa.Column("value_number", sa.Numeric(12, 2), nullable=True),
            sa.Column("media_id", sa.Integer(), sa.ForeignKey("media.id", ondelete="SET NULL"), nullable=True),
            sa.Column(
                "answered_by_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("answered_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "request_id", "template_item_id", name="uq_request_checklist_answer"
            ),
        )
    if not index_exists(conn, "request_checklist_answers", "ix_request_checklist_answers_request_id"):
        op.create_index(
            "ix_request_checklist_answers_request_id",
            "request_checklist_answers",
            ["request_id"],
        )
    if not index_exists(conn, "request_checklist_answers", "ix_request_checklist_answers_template_item_id"):
        op.create_index(
            "ix_request_checklist_answers_template_item_id",
            "request_checklist_answers",
            ["template_item_id"],
        )

    has_default = conn.execute(
        sa.text("SELECT 1 FROM checklist_templates WHERE is_default = true LIMIT 1")
    ).first()
    if not has_default:
        op.execute(
            sa.text(
                """
                INSERT INTO checklist_templates (name, equipment_type, is_default, is_active)
                VALUES ('Универсальный шаблон', NULL, true, true)
                """
            )
        )
        op.execute(
            sa.text(
                """
                INSERT INTO checklist_template_items (template_id, title, item_order, is_required, item_type)
                SELECT id, 'Проверка состояния оборудования', 10, true, 'boolean'
                FROM checklist_templates
                WHERE is_default = true
                """
            )
        )
        op.execute(
            sa.text(
                """
                INSERT INTO checklist_template_items (template_id, title, item_order, is_required, item_type)
                SELECT id, 'Подтверждение выполненных работ', 20, true, 'boolean'
                FROM checklist_templates
                WHERE is_default = true
                """
            )
        )


def downgrade():
    conn = op.get_bind()
    if index_exists(conn, "request_checklist_answers", "ix_request_checklist_answers_template_item_id"):
        op.drop_index(
            "ix_request_checklist_answers_template_item_id",
            table_name="request_checklist_answers",
        )
    if index_exists(conn, "request_checklist_answers", "ix_request_checklist_answers_request_id"):
        op.drop_index(
            "ix_request_checklist_answers_request_id", table_name="request_checklist_answers"
        )
    if table_exists(conn, "request_checklist_answers"):
        op.drop_table("request_checklist_answers")

    if index_exists(conn, "checklist_template_items", "ix_checklist_template_items_template_id"):
        op.drop_index(
            "ix_checklist_template_items_template_id", table_name="checklist_template_items"
        )
    if table_exists(conn, "checklist_template_items"):
        op.drop_table("checklist_template_items")

    if index_exists(conn, "checklist_templates", "ix_checklist_templates_equipment_type"):
        op.drop_index("ix_checklist_templates_equipment_type", table_name="checklist_templates")
    if table_exists(conn, "checklist_templates"):
        op.drop_table("checklist_templates")
