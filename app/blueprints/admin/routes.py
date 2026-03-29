# Path: app/blueprints/admin/routes.py
from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.blueprints.admin import admin_bp
from app.models.all_models import Users


@admin_bp.route("/")
@login_required
def index():
    if current_user.role != "admin":
        flash("Доступ только для администратора.", "danger")
        return redirect(url_for("auth.login"))
    users = Users.query.order_by(Users.username).all()
    return render_template("admin/index.html", users=users)
