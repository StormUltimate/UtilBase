# Path: app/blueprints/users/routes.py
from datetime import datetime
from urllib.parse import urlparse

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.all_models import Users, Worker

from . import users_bp
from .forms import UserForm


def _safe_next_url(default_url):
    raw = (request.args.get("next") if request.method == "GET" else request.form.get("next")) or ""
    raw = raw.strip()
    if raw and raw.startswith("/"):
        parsed = urlparse(raw)
        if not parsed.scheme and not parsed.netloc:
            return raw
    return default_url


EXECUTOR_ROLES = {"master", "engineer"}


def _sync_user_worker_profile(user: Users, full_name: str, phone: str) -> None:
    full_name = (full_name or "").strip()
    phone = (phone or "").strip() or None
    worker = user.linked_worker

    if user.role in EXECUTOR_ROLES:
        if not full_name:
            raise ValueError("Для роли master/engineer заполните ФИО.")
        if worker is None and user.worker_id:
            worker = Worker.query.get(user.worker_id)
        if worker is None:
            worker = Worker(
                full_name=full_name,
                phone=phone,
                role=user.role,
                is_active=True,
            )
            db.session.add(worker)
            db.session.flush()
            user.worker_id = worker.id
        else:
            worker.full_name = full_name
            worker.phone = phone
            worker.role = user.role
            worker.is_active = True
            worker.inactive_at = None
            user.worker_id = worker.id
    else:
        if worker and worker.is_active:
            worker.is_active = False
            worker.inactive_at = datetime.utcnow()
        user.worker_id = None


@users_bp.route("/", methods=["GET"])
@login_required
def list_users():
    return redirect(url_for("admin.index"))


@users_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_user():
    form = UserForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        role = form.role.data
        full_name = form.full_name.data or ""
        phone = form.phone.data or ""
        if not password:
            flash("Укажите пароль.", "error")
            return render_template("users/add.html", form=form)
        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            flash("Имя пользователя уже существует", "error")
            return render_template("users/add.html", form=form)
        new_user = Users(
            username=username,
            password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
            role=role,
        )
        db.session.add(new_user)
        db.session.flush()
        try:
            _sync_user_worker_profile(new_user, full_name, phone)
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            return render_template("users/add.html", form=form)
        db.session.commit()
        flash("Пользователь добавлен", "success")
        return redirect(url_for("admin.index"))
    return render_template("users/add.html", form=form)


@users_bp.route("/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    user = Users.query.get_or_404(user_id)
    next_url = _safe_next_url(url_for("admin.index"))
    form = UserForm(obj=user)
    if request.method == "GET":
        form.full_name.data = user.linked_worker.full_name if user.linked_worker else ""
        form.phone.data = user.linked_worker.phone if user.linked_worker else ""
    if form.validate_on_submit():
        existing_other = Users.query.filter(
            Users.username == form.username.data, Users.id != user.id
        ).first()
        if existing_other:
            flash("Имя пользователя уже существует", "error")
            return render_template("users/edit.html", form=form, user=user, next_url=next_url)
        user.username = form.username.data
        if form.password.data:
            user.password_hash = generate_password_hash(form.password.data, method="pbkdf2:sha256")
        user.role = form.role.data
        try:
            _sync_user_worker_profile(user, form.full_name.data or "", form.phone.data or "")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            return render_template("users/edit.html", form=form, user=user, next_url=next_url)
        db.session.commit()
        flash("Пользователь обновлён", "success")
        return redirect(next_url)
    return render_template("users/edit.html", form=form, user=user, next_url=next_url)


@users_bp.route("/delete", methods=["GET"])
@login_required
def delete_user_redirect():
    return redirect(url_for("admin.index"))


@users_bp.route("/delete/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash("Нельзя удалить самого себя.", "danger")
        return redirect(url_for("admin.index"))
    user = Users.query.get_or_404(user_id)
    if user.linked_worker and user.linked_worker.is_active:
        user.linked_worker.is_active = False
        user.linked_worker.inactive_at = datetime.utcnow()
    db.session.delete(user)
    db.session.commit()
    flash("Пользователь удалён", "success")
    return redirect(url_for("admin.index"))
