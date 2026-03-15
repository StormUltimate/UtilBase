# Path: app/blueprints/photos/__init__.py
# New file: Blueprint для photos.
from flask import Blueprint

photos_bp = Blueprint('photos', __name__, template_folder='../templates/photos')

from .routes import *