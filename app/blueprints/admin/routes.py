# Path: app/blueprints/admin/routes.py
from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.blueprints.admin import admin_bp
from app.models.all_models import Users, Worker


@admin_bp.route('/')
@login_required
def index():
    if current_user.role != 'admin':
        flash('Доступ только для администратора.', 'danger')
        return redirect(url_for('auth.login'))
    users = Users.query.order_by(Users.username).all()
    workers = Worker.query.order_by(Worker.full_name).all()
    return render_template('admin/index.html', users=users, workers=workers)
