# File: app/blueprints/main/routes.py
from flask import Blueprint, render_template
from flask_login import login_required

main_bp = Blueprint('main', __name__, template_folder='templates')

@main_bp.route('/home')
@login_required
def index():
    return render_template('main/index.html')