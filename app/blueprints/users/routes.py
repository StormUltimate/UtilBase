# Path: app/blueprints/users/routes.py
from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models.all_models import Users
from .forms import UserForm
from . import users_bp

@users_bp.route('/', methods=['GET'])
@login_required
def list_users():
    return redirect(url_for('admin.index'))

@users_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_user():
    form = UserForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        role = form.role.data
        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            flash('Имя пользователя уже существует', 'error')
            return render_template('users/add.html', form=form)
        new_user = Users(
            username=username,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
            role=role,
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Пользователь добавлен', 'success')
        return redirect(url_for('admin.index'))
    return render_template('users/add.html', form=form)

@users_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user = Users.query.get_or_404(user_id)
    form = UserForm(obj=user)
    if form.validate_on_submit():
        user.username = form.username.data
        if form.password.data:
            user.password_hash = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        user.role = form.role.data
        db.session.commit()
        flash('Пользователь обновлён', 'success')
        return redirect(url_for('admin.index'))
    return render_template('users/edit.html', form=form, user=user)

@users_bp.route('/delete', methods=['GET'])
@login_required
def delete_user_redirect():
    return redirect(url_for('admin.index'))


@users_bp.route('/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Нельзя удалить самого себя.', 'danger')
        return redirect(url_for('admin.index'))
    user = Users.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('Пользователь удалён', 'success')
    return redirect(url_for('admin.index'))