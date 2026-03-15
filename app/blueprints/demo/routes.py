# Path: app/blueprints/demo/routes.py
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user

from . import demo_bp
from app.utils.demo_db import create_demo_data, delete_demo_data


@demo_bp.route('/')
@login_required
def index():
    if current_user.role != 'admin':
        flash('Доступ только для администратора.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('demo/index.html')


@demo_bp.route('/create', methods=['POST'])
@login_required
def create():
    if current_user.role != 'admin':
        flash('Доступ только для администратора.', 'danger')
        return redirect(url_for('auth.login'))
    try:
        create_demo_data(app=current_app._get_current_object())
        flash('Демо-данные созданы: клиенты, договоры, заявки (часть закрытых), исполнители, записи фото.', 'success')
    except Exception as e:
        flash(f'Ошибка при создании демо-данных: {e}', 'danger')
    return redirect(url_for('admin.index'))


@demo_bp.route('/delete', methods=['POST'])
@login_required
def delete():
    if current_user.role != 'admin':
        flash('Доступ только для администратора.', 'danger')
        return redirect(url_for('auth.login'))
    try:
        delete_demo_data()
        flash('Все демо-данные удалены.', 'success')
    except Exception as e:
        flash(f'Ошибка при удалении демо-данных: {e}', 'danger')
    return redirect(url_for('admin.index'))
