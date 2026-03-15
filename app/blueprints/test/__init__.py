# Path: app/blueprints/test/__init__.py
from flask import Blueprint

test_bp = Blueprint('test', __name__, template_folder='templates')

from . import routes