"""link checklist templates to equipment and request

Revision ID: w1x2y3z4a5b6
Revises: v0w1x2y3z4a5
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa

from migrations.schema_util import column_exists, constraint_exists, index_exists

revision = "w1x2y3z4a5b6"
down_revision = "v0w1x2y3z4a5"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if not column_exists(conn, "checklist_templates", "equipment_id"):
        op.add_column("checklist_templates", sa.Column("equipment_id", sa.Integer(), nullable=True))
    if not constraint_exists(conn, "checklist_templates", "fk_checklist_templates_equipment_id"):
        op.create_foreign_key(
            "fk_checklist_templates_equipment_id",
            "checklist_templates",
            "equipment",
            ["equipment_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not index_exists(conn, "checklist_templates", "ix_checklist_templates_equipment_id"):
        op.create_index(
            "ix_checklist_templates_equipment_id", "checklist_templates", ["equipment_id"]
        )

    if not column_exists(conn, "requests", "checklist_template_id"):
        op.add_column("requests", sa.Column("checklist_template_id", sa.Integer(), nullable=True))
    if not constraint_exists(conn, "requests", "fk_requests_checklist_template_id"):
        op.create_foreign_key(
            "fk_requests_checklist_template_id",
            "requests",
            "checklist_templates",
            ["checklist_template_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not index_exists(conn, "requests", "ix_requests_checklist_template_id"):
        op.create_index(
            "ix_requests_checklist_template_id", "requests", ["checklist_template_id"]
        )


def downgrade():
    conn = op.get_bind()
    if index_exists(conn, "requests", "ix_requests_checklist_template_id"):
        op.drop_index("ix_requests_checklist_template_id", table_name="requests")
    if constraint_exists(conn, "requests", "fk_requests_checklist_template_id"):
        op.drop_constraint("fk_requests_checklist_template_id", "requests", type_="foreignkey")
    if column_exists(conn, "requests", "checklist_template_id"):
        op.drop_column("requests", "checklist_template_id")

    if index_exists(conn, "checklist_templates", "ix_checklist_templates_equipment_id"):
        op.drop_index("ix_checklist_templates_equipment_id", table_name="checklist_templates")
    if constraint_exists(conn, "checklist_templates", "fk_checklist_templates_equipment_id"):
        op.drop_constraint(
            "fk_checklist_templates_equipment_id", "checklist_templates", type_="foreignkey"
        )
    if column_exists(conn, "checklist_templates", "equipment_id"):
        op.drop_column("checklist_templates", "equipment_id")
