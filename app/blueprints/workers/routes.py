# Path: V:\UtilBase\app\blueprints\workers\routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.all_models import Worker

workers_bp = Blueprint('workers', __name__)  # Шаблоны лежат в app/templates/workers/


@workers_bp.route('/', methods=['GET'])
@login_required
def index():
    return redirect(url_for('admin.index'))


@workers_bp.route('/list', methods=['GET'])
@login_required
def list_workers():
    return redirect(url_for('admin.index'))


@workers_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_worker():
    if current_user.role != 'admin':
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        role = request.form.get('role')  # 'master' или 'engineer'
        if not full_name or not role:
            flash('Заполните обязательные поля (ФИО и роль).', 'danger')
            return redirect(url_for('workers.create_worker'))
        new_worker = Worker(full_name=full_name, phone=phone or None, role=role)
        db.session.add(new_worker)
        db.session.commit()
        flash('Исполнитель создан.', 'success')
        return redirect(url_for('admin.index'))
    return render_template('workers/workers_create.html')


@workers_bp.route('/edit/<int:worker_id>', methods=['GET', 'POST'])
@login_required
def edit_worker(worker_id):
    if current_user.role != 'admin':
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('auth.login'))
    worker = Worker.query.get_or_404(worker_id)
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        role = request.form.get('role')
        if not full_name or not role:
            flash('Заполните обязательные поля (ФИО и роль).', 'danger')
            return redirect(url_for('workers.edit_worker', worker_id=worker.id))
        worker.full_name = full_name
        worker.phone = phone or None
        worker.role = role
        db.session.commit()
        flash('Исполнитель обновлён.', 'success')
        return redirect(url_for('admin.index'))
    return render_template('workers/workers_edit.html', worker=worker)


@workers_bp.route('/delete/<int:worker_id>', methods=['POST'])
@login_required
def delete_worker(worker_id):
    if current_user.role != 'admin':
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('auth.login'))
    worker = Worker.query.get_or_404(worker_id)
    db.session.delete(worker)
    db.session.commit()
    flash('Исполнитель удалён.', 'success')
    return redirect(url_for('admin.index'))