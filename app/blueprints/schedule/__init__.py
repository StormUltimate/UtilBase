"""План-график: отдельный blueprint (можно переносить в другой проект)."""

from flask import Blueprint

schedule_bp = Blueprint("schedule", __name__, url_prefix="/schedule")

from app.blueprints.schedule import routes  # noqa: E402, F401
