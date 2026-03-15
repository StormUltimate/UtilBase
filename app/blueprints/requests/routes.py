# Path: V:\UtilBase\app\blueprints\requests\routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.all_models import Request, Client, Worker, RequestStatus, Contract, Equipment, WorkOrder, Media
from .forms import RequestForm
from datetime import datetime, date
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, or_

requests_bp = Blueprint('requests', __name__)

@requests_bp.before_request
def before_request():
    try:
        overdue_requests = Request.query.filter(
            Request.planned_date < date.today(),
            Request.status.notin_(['closed', 'overdue'])
        ).all()
        for req in overdue_requests:
            req.status = 'overdue'
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'danger')

@requests_bp.route('/')
@requests_bp.route('/list')
@login_required
def list_requests():
    filter_type = request.args.get('filter', 'all')
    type_filter = request.args.get('type', '')
    status_filter = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search_client = request.args.get('search', '').strip()

    from .forms import RequestForm  # локальный импорт, чтобы избежать циклов
    try:
        base_query = Request.query
        if filter_type == 'today':
            base_query = base_query.filter(func.date(Request.planned_date) == date.today())
        elif filter_type == 'planned':
            base_query = base_query.filter(Request.planned_date > datetime.now(), Request.status.notin_(['closed', 'canceled']))
        elif filter_type == 'overdue':
            base_query = base_query.filter(Request.status == 'overdue')

        if type_filter:
            type_map = {'emergency': ['аварийная', 'emergency'], 'repair': ['ремонтная', 'repair'], 'planned': ['плановая', 'planned']}
            if type_filter in type_map:
                base_query = base_query.filter(or_(Request.type.in_(type_map[type_filter]), Request.service_type == type_filter))

        if status_filter:
            try:
                base_query = base_query.filter(Request.status == RequestStatus(status_filter))
            except ValueError:
                pass

        if date_from:
            try:
                df = datetime.strptime(date_from, '%Y-%m-%d').date()
                base_query = base_query.filter(Request.planned_date >= df)
            except ValueError:
                pass
        if date_to:
            try:
                dt = datetime.strptime(date_to, '%Y-%m-%d').date()
                base_query = base_query.filter(Request.planned_date <= dt)
            except ValueError:
                pass

        if search_client:
            term = f'%{search_client}%'
            base_query = base_query.outerjoin(Client, Request.client_id == Client.id).filter(
                or_(
                    Client.full_name.ilike(term),
                    Client.address.ilike(term),
                    Client.phone.ilike(term),
                    Request.full_name.ilike(term),
                    Request.address.ilike(term),
                    Request.phone.ilike(term)
                )
            )

        if current_user.role in ['engineer', 'master']:
            base_query = base_query.filter(Request.workers.any(id=current_user.id))

        requests = base_query.order_by(Request.planned_date.desc().nullslast(), Request.created_at.desc()).all()
        request_form = None
        if current_user.role == 'admin':
            request_form = RequestForm()
            request_form.client_id.choices = [(0, 'Нет')] + [(c.id, c.full_name) for c in Client.query.all()]
            request_form.contract_id.choices = [(0, 'Нет')] + [(c.id, c.contract_type or f'Договор #{c.id}') for c in Contract.query.all()]
            request_form.equipment_id.choices = [(0, 'Нет')] + [(e.id, e.model or e.serial_number or f'Оборудование #{e.id}') for e in Equipment.query.all()]
            request_form.workers.choices = [(w.id, w.full_name) for w in Worker.query.all()]
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'danger')
        requests = []
        request_form = None

    return render_template(
        'requests/list.html' if current_user.role == 'admin' else 'requests/list_mobile.html',
        requests=requests, filter=filter_type,
        type_filter=type_filter, status_filter=status_filter,
        date_from=date_from, date_to=date_to, search_client=search_client,
        request_form=request_form
    )

@requests_bp.route('/today')
@login_required
def today_requests():
    if current_user.role != 'admin':
        flash('Доступ только для админа.', 'danger')
        return redirect(url_for('requests.list_requests'))
    
    filter_type = request.args.get('filter_type', 'today')
    client_id = request.args.get('client_id')
    worker_id = request.args.get('worker_id')
    service_type = request.args.get('service_type')
    status = request.args.get('status')
    sort_by = request.args.get('sort_by', 'planned_date')
    sort_order = request.args.get('sort_order', 'asc')
    
    try:
        base_query = Request.query
        if filter_type == 'today':
            base_query = base_query.filter(func.date(Request.planned_date) == date.today())
        elif filter_type == 'overdue':
            base_query = base_query.filter(Request.status == 'overdue')
        elif filter_type == 'specific_date':
            specific_date = request.args.get('specific_date')
            if specific_date:
                base_query = base_query.filter(func.date(Request.planned_date) == datetime.strptime(specific_date, '%Y-%m-%d').date())
        
        if client_id and client_id != 'all':
            base_query = base_query.filter(Request.client_id == int(client_id))
        if worker_id and worker_id != 'all':
            base_query = base_query.filter(Request.workers.any(id=int(worker_id)))
        if service_type and service_type != 'all':
            base_query = base_query.filter(Request.service_type == service_type)
        if status and status != 'all':
            base_query = base_query.filter(Request.status == status)
        
        if sort_by:
            order_col = getattr(Request, sort_by)
            if sort_order == 'desc':
                order_col = order_col.desc()
            base_query = base_query.order_by(order_col)
        
        requests = base_query.all()
        overdue_count = Request.query.filter(Request.status == 'overdue').count()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'danger')
        requests = []
        overdue_count = 0

    clients = Client.query.all()
    workers = Worker.query.all()
    return render_template('requests/today.html', requests=requests, filter_type=filter_type, overdue_count=overdue_count, clients=clients, workers=workers)

@requests_bp.route('/api/search_clients')
@login_required
def search_clients():
    query = request.args.get('query', '')
    clients = Client.query.filter(or_(Client.full_name.ilike(f'%{query}%'), Client.phone.ilike(f'%{query}%'), Client.address.ilike(f'%{query}%'))).limit(10).all()
    results = [{'id': c.id, 'text': f'{c.full_name} ({c.phone}) - {c.address}'} for c in clients]
    return jsonify({'results': results})

@requests_bp.route('/api/get_client/<int:id>')
@login_required
def get_client(id):
    client = Client.query.get(id)
    if client:
        return jsonify({
            'full_name': client.full_name,
            'address': client.address,
            'phone': client.phone
        })
    return jsonify({}), 404

@requests_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_request():
    if current_user.role != 'admin':
        flash('Доступ только для админа.', 'danger')
        return redirect(url_for('requests.list_requests'))
    form = RequestForm()
    form.client_id.choices = [(0, 'Нет')] + [(c.id, c.full_name) for c in Client.query.all()]
    form.contract_id.choices = [(0, 'Нет')] + [(c.id, c.contract_type) for c in Contract.query.all()]
    form.equipment_id.choices = [(0, 'Нет')] + [(e.id, e.model) for e in Equipment.query.all()]
    form.workers.choices = [(w.id, w.full_name) for w in Worker.query.all()]
    if form.validate_on_submit():
        try:
            client_id = form.client_id.data if form.client_id.data != 0 else None
            if client_id is None:
                if not form.full_name.data or not form.address.data:
                    flash('Укажите клиента или ФИО и адрес.', 'danger')
                    return render_template('requests/add.html', form=form)
                # Создание нового клиента
                new_client = Client(
                    full_name=form.full_name.data,
                    address=form.address.data,
                    phone=form.phone.data
                )
                db.session.add(new_client)
                db.session.commit()
                client_id = new_client.id
            type_map = {'emergency': 'аварийная', 'repair': 'ремонтная', 'planned': 'плановая'}
            req_type = type_map.get(form.type.data, '') if form.type.data else None
            req = Request(
                client_id=client_id,
                full_name=form.full_name.data,
                address=form.address.data,
                phone=form.phone.data,
                description=form.description.data,
                type=req_type,
                service_type=form.service_type.data,
                warranty_reason=form.warranty_reason.data,
                urgent_price=form.urgent_price.data,
                contract_regulated_price=form.contract_regulated_price.data,
                materials_cost=form.materials_cost.data,
                total_price=form.total_price.data,
                estimated_time=form.estimated_time.data,
                planned_date=form.planned_date.data,
                planned_start_time=form.planned_start_time.data,
                planned_end_time=form.planned_end_time.data,
                status=form.status.data or 'pending',
                mode=form.mode.data or 'normal',
                created_by_user_id=current_user.id
            )
            db.session.add(req)
            db.session.commit()
            req.request_number = f'REQ-{req.id:06d}'
            for worker_id in form.workers.data:
                worker = Worker.query.get(worker_id)
                req.workers.append(worker)
            db.session.commit()
            flash('Заявка добавлена.', 'success')
            return redirect(url_for('requests.list_requests'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    return render_template('requests/add.html', form=form)

@requests_bp.route('/view/<int:id>', methods=['GET'])
@login_required
def view_request(id):
    req = Request.query.get_or_404(id)
    if current_user.role not in ['admin'] and not any(w.id == current_user.id for w in req.workers):
        flash('Доступ только к своим заявкам.', 'danger')
        return redirect(url_for('requests.list_requests'))
    return render_template('requests/view.html', req=req)

@requests_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_request(id):
    if current_user.role != 'admin':
        flash('Доступ только для админа.', 'danger')
        return redirect(url_for('requests.list_requests'))
    req = Request.query.get_or_404(id)
    form = RequestForm(obj=req)
    type_reverse = {'аварийная': 'emergency', 'emergency': 'emergency', 'ремонтная': 'repair', 'repair': 'repair', 'плановая': 'planned', 'planned': 'planned'}
    form.type.data = type_reverse.get(req.type, 'planned') if req.type else 'planned'
    form.client_id.choices = [(0, 'Нет')] + [(c.id, c.full_name) for c in Client.query.all()]
    form.contract_id.choices = [(0, 'Нет')] + [(c.id, c.contract_type) for c in Contract.query.all()]
    form.equipment_id.choices = [(0, 'Нет')] + [(e.id, e.model) for e in Equipment.query.all()]
    form.workers.choices = [(w.id, w.full_name) for w in Worker.query.all()]
    form.workers.data = [w.id for w in req.workers]
    if form.validate_on_submit():
        try:
            client_id = form.client_id.data if form.client_id.data != 0 else None
            if client_id is None:
                if not form.full_name.data or not form.address.data:
                    flash('Укажите клиента или ФИО и адрес.', 'danger')
                    return render_template('requests/edit.html', form=form, req=req)
                # Создание нового клиента, если не выбран существующий
                new_client = Client(
                    full_name=form.full_name.data,
                    address=form.address.data,
                    phone=form.phone.data
                )
                db.session.add(new_client)
                db.session.commit()
                client_id = new_client.id
            req.client_id = client_id
            req.full_name = form.full_name.data
            req.address = form.address.data
            req.phone = form.phone.data
            req.description = form.description.data
            req.type = {'emergency': 'аварийная', 'repair': 'ремонтная', 'planned': 'плановая'}.get(form.type.data, '') if form.type.data else None
            req.service_type = form.service_type.data
            req.warranty_reason = form.warranty_reason.data
            req.urgent_price = form.urgent_price.data
            req.contract_regulated_price = form.contract_regulated_price.data
            req.materials_cost = form.materials_cost.data
            req.total_price = form.total_price.data
            req.estimated_time = form.estimated_time.data
            req.planned_date = form.planned_date.data
            req.planned_start_time = form.planned_start_time.data
            req.planned_end_time = form.planned_end_time.data
            req.status = form.status.data
            req.mode = form.mode.data
            req.updated_by_user_id = current_user.id
            req.updated_at = datetime.utcnow()
            req.workers = []
            for worker_id in form.workers.data:
                worker = Worker.query.get(worker_id)
                req.workers.append(worker)
            db.session.commit()
            flash('Заявка обновлена.', 'success')
            return redirect(url_for('requests.list_requests'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    return render_template('requests/edit.html', form=form, req=req)

@requests_bp.route('/create_work_order/<int:id>', methods=['GET', 'POST'])
@login_required
def create_work_order(id):
    if current_user.role != 'admin':
        flash('Доступ только для админа.', 'danger')
        return redirect(url_for('requests.list_requests'))
    req = Request.query.get_or_404(id)
    # Логика создания наряда (work order)
    # Пока просто создание пустого наряда
    work_order = WorkOrder(
        request_id = req.id,
        description = 'Наряд для заявки #' + req.request_number,
        created_at = datetime.utcnow()
    )
    db.session.add(work_order)
    db.session.commit()
    flash('Наряд создан.', 'success')
    return redirect(url_for('requests.view_request', id=id))

@requests_bp.route('/assign/<int:id>', methods=['POST'])
@login_required
def assign_request(id):
    req = Request.query.get_or_404(id)
    worker = Worker.query.filter_by(id=current_user.id).first()
    if worker and worker not in req.workers:
        req.workers.append(worker)
        if req.status == 'pending':
            req.status = 'assigned'
        db.session.commit()
        flash('Заявка присвоена.', 'success')
    return redirect(url_for('requests.list_requests'))

@requests_bp.route('/assign_worker', methods=['POST'])
@login_required
def assign_worker():
    if current_user.role != 'admin':
        flash('Доступ только для админа.', 'danger')
        return redirect(url_for('requests.today_requests'))
    worker_id = request.form.get('worker_id')
    request_ids = request.form.getlist('request_ids')
    worker = Worker.query.get(worker_id)
    if not worker:
        flash('Мастер не найден.', 'danger')
        return redirect(url_for('requests.today_requests'))
    for req_id in request_ids:
        req = Request.query.get(req_id)
        if req and worker not in req.workers:
            req.workers.append(worker)
            if req.status == 'pending':
                req.status = 'assigned'
    db.session.commit()
    flash('Мастер назначен.', 'success')
    return redirect(url_for('requests.today_requests'))

@requests_bp.route('/close/<int:id>', methods=['POST'])
@login_required
def close_request(id):
    req = Request.query.get_or_404(id)
    if current_user.role not in ['engineer', 'master'] or not any(w.id == current_user.id for w in req.workers):
        flash('Доступ только для назначенного мастера.', 'danger')
        return redirect(url_for('requests.list_requests'))
    # Закомментировано: чек-лист процедура
    # form = ChecklistForm()
    # if form.validate_on_submit():
    #     # Сохранить чек-лист (галочки/комментарий) в JSON или таблицу
    #     req.status = 'closed'
    #     req.actual_end_time = datetime.utcnow()
    #     db.session.commit()
    #     flash('Заявка закрыта после чек-листа.', 'success')
    # else:
    #     return render_template('requests/close.html', form=form, req=req)
    # Пока просто закрытие
    req.status = 'closed'
    db.session.commit()
    flash('Заявка закрыта (чек-лист закомментирован).', 'success')
    return redirect(url_for('requests.list_requests'))


@requests_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_request(id):
    if current_user.role != 'admin':
        flash('Доступ только для админа.', 'danger')
        return redirect(url_for('requests.list_requests'))
    req = Request.query.get_or_404(id)
    try:
        # Отвязываем медиа, чтобы не потерять фото/файлы
        Media.query.filter_by(request_id=req.id).update({Media.request_id: None})
        db.session.delete(req)
        db.session.commit()
        flash('Заявка удалена. Связанные медиа сохранены.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка при удалении заявки: {str(e)}', 'danger')
    return redirect(url_for('requests.list_requests'))

@requests_bp.route('/calendar')
@login_required
def calendar():
    clients = Client.query.all()
    workers = Worker.query.all()
    statuses = [s.value for s in RequestStatus]
    template = 'requests/calendar.html' if current_user.role == 'admin' else 'requests/calendar_mobile.html'
    return render_template(template, clients=clients, workers=workers, statuses=statuses)

@requests_bp.route('/api/events')
@login_required
def api_events():
    events = []
    for req in Request.query.all():
        if req.planned_date:
            title = req.description or 'Заявка'
            if req.client_id and req.client:
                title += f' для {req.client.full_name}'
            elif req.full_name:
                title += f' для {req.full_name}'
            workers_names = ', '.join([w.full_name for w in req.workers])
            if workers_names:
                title += f' ({workers_names})'
            # Цвет по типу: аварийная=red, ремонтная=orange, плановая=green; статус overdue=red
            req_type = req.type or (req.service_type.value if req.service_type else '')
            if req.status and req.status.value == 'overdue':
                color = '#dc3545'
            elif req.status and req.status.value == 'closed':
                color = '#198754'
            elif req_type in ['аварийная', 'emergency']:
                color = '#dc3545'
            elif req_type in ['ремонтная', 'repair']:
                color = '#fd7e14'
            elif req_type in ['плановая', 'planned']:
                color = '#198754'
            elif req.status and req.status.value == 'assigned':
                color = '#0d6efd'
            else:
                color = '#6c757d'
            events.append({
                'id': req.id,
                'title': title,
                'start': req.planned_date.isoformat(),
                'color': color
            })
    if current_user.role in ['engineer', 'master']:
        events = [e for e in events if any(w.id == current_user.id for w in Request.query.get(e['id']).workers)]
    return jsonify(events)

@requests_bp.route('/api/update_event', methods=['POST'])
@login_required
def api_update_event():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ только для админа'})
    data = request.json
    req = Request.query.get_or_404(data['id'])
    req.planned_date = datetime.fromisoformat(data['start'])
    db.session.commit()
    return jsonify({'success': True})