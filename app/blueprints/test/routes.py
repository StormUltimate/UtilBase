# Path: app/blueprints/test/routes.py
from flask import render_template
from flask_login import login_required
from . import test_bp

@test_bp.route('/')
@login_required
def index():
    return render_template('test/test.html')