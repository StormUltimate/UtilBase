"""REST API v1."""

from flask import Blueprint

api_v1_bp = Blueprint("api_v1", __name__)

from app.api.v1 import (
    auth,  # noqa: E402, F401
    checklist_admin_routes,  # noqa: E402, F401
    checklist_routes,  # noqa: E402, F401
    requests_extras,  # noqa: E402, F401
    requests_routes,  # noqa: E402, F401
)
