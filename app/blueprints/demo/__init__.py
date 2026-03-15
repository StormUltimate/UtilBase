# Path: app/blueprints/demo/__init__.py
from flask import Blueprint

demo_bp = Blueprint('demo', __name__)

from app.blueprints.demo import routes  # noqa: E402, F401
