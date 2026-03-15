# Path: app/blueprints/clients/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from io import BytesIO
from datetime import date, datetime
import pandas as pd
import requests
from app.extensions import db
from app.models.all_models import Client, Request, Contract, Media, Payment, Nomenclature, Equipment, EquipmentTemplate
from flask_login import login_required
from app.utils.logger import log
from .forms import ClientForm, ClientDeleteForm
from sqlalchemy.exc import SQLAlchemyError  # Added import to fix NameError

clients_bp = Blueprint('clients', __name__, url_prefix='/clients')

@clients_bp.route('/', methods=['GET'])
@login_required
def clients():
    search_term = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'id')
    sort_order = request.args.get('sort_order', 'asc')
    counterparty_filter = request.args.get('counterparty_filter', '')
    client_id = request.args.get('client_id', '')

    clients_query = Client.query.filter(
        db.or_(
            Client.full_name.ilike(f'%{search_term}%'),
            Client.address.ilike(f'%{search_term}%'),
            Client.phone.ilike(f'%{search_term}%')
        )
    )
    if counterparty_filter and counterparty_filter != 'Все':
        clients_query = clients_query.filter(Client.counterparty == counterparty_filter)
    if sort_by == 'full_name':
        clients_query = clients_query.order_by(Client.full_name.asc() if sort_order == 'asc' else Client.full_name.desc())
    elif sort_by == 'created_at':
        clients_query = clients_query.order_by(Client.created_at.asc() if sort_order == 'asc' else Client.created_at.desc())
    else:
        clients_query = clients_query.order_by(Client.id.asc() if sort_order == 'asc' else Client.id.desc())
    clients = clients_query.all()

    counterparties = [cp[0] for cp in db.session.query(Client.counterparty).distinct().all() if cp[0]]
    counterparties.insert(0, 'Все')

    client_requests = []
    if client_id:
        client_requests = Request.query.filter_by(client_id=int(client_id)).order_by(Request.created_at.desc()).all()

    return render_template(
        'clients/list.html',
        clients=clients,
        client_requests=client_requests,
        search_term=search_term,
        sort_by=sort_by,
        sort_order=sort_order,
        counterparties=counterparties,
        counterparty_filter=counterparty_filter,
        client_form=ClientForm(),
        delete_form=ClientDeleteForm(),
    )

@clients_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_client():
    form = ClientForm()
    if form.validate_on_submit():
        full_name = form.full_name.data
        phone = form.phone.data
        address = form.address.data
        representative_name = form.representative_name.data
        representative_phone = form.representative_phone.data
        email = form.email.data

        latitude = None
        longitude = None
        if address:
            try:
                response = requests.get(
                    f'https://geocode-maps.yandex.ru/1.x/?apikey=3ef709e6-31eb-4c3c-a488-4f08ddbd5caf&geocode={address}&format=json'
                )
                data = response.json()
                if data['response']['GeoObjectCollection']['featureMember']:
                    coords = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point']['pos']
                    longitude, latitude = map(float, coords.split())
            except Exception as e:
                flash(f'Ошибка геокодирования: {str(e)}', 'warning')

        new_client = Client(
            full_name=full_name,
            phone=phone,
            address=address,
            representative_name=representative_name or None,
            representative_phone=representative_phone or None,
            email=email or None,
            latitude=latitude,
            longitude=longitude
        )
        db.session.add(new_client)
        db.session.commit()
        log.info('Клиент успешно добавлен')
        flash('Клиент успешно добавлен', 'success')
        return redirect(url_for('clients.clients'))
    return render_template('clients/add.html', form=form)

@clients_bp.route('/edit/<int:client_id>', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    form = ClientForm(obj=client)
    if form.validate_on_submit():
        # Обновляем основные поля
        client.full_name = form.full_name.data
        client.phone = form.phone.data
        client.address = form.address.data
        client.representative_name = form.representative_name.data or None
        client.representative_phone = form.representative_phone.data or None
        client.email = form.email.data or None

        # Сброс координат по запросу пользователя
        if form.reset_coords.data:
            client.latitude = None
            client.longitude = None

        # Пересчитываем координаты, если есть адрес и координаты пустые
        if client.address and (client.latitude is None or client.longitude is None):
            try:
                response = requests.get(
                    f'https://geocode-maps.yandex.ru/1.x/?apikey=3ef709e6-31eb-4c3c-a488-4f08ddbd5caf&geocode={client.address}&format=json'
                )
                data = response.json()
                if data['response']['GeoObjectCollection']['featureMember']:
                    coords = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point']['pos']
                    client.longitude, client.latitude = map(float, coords.split())
            except Exception as e:
                flash(f'Ошибка геокодирования: {str(e)}', 'warning')

        db.session.commit()
        log.info('Клиент успешно обновлён')
        flash('Клиент успешно обновлён', 'success')
        return redirect(url_for('clients.clients'))
    return render_template('clients/edit.html', form=form, client=client)

@clients_bp.route('/delete', methods=['GET', 'POST'])
@login_required
def delete_client():
    form = ClientDeleteForm()
    if form.validate_on_submit():
        client_id = form.client_id.data
        client = Client.query.get(client_id)
        if client:
            try:
                db.session.delete(client)
                db.session.commit()
                log.info(f'Клиент с ID {client_id} удалён')
                flash(f'Клиент с ID {client_id} удалён', 'success')
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f'Ошибка удаления: {str(e)}', 'error')
        else:
            flash('Клиент не найден', 'error')
        return redirect(url_for('clients.clients'))
    return render_template('clients/delete.html', form=form)

@clients_bp.route('/detail/<int:client_id>')
@login_required
def client_detail(client_id):
    from sqlalchemy import func
    client = Client.query.get_or_404(client_id)
    req_type = request.args.get('type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search_desc = request.args.get('search', '')
    requests_query = Request.query.filter_by(client_id=client_id)
    if req_type:
        type_map = {'аварийные': ['аварийная', 'emergency'], 'ремонтные': ['ремонтная'], 'плановые': ['плановая']}
        if req_type in type_map:
            requests_query = requests_query.filter(Request.type.in_(type_map[req_type]))
    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d')
            requests_query = requests_query.filter(func.date(Request.created_at) >= df.date())
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d')
            requests_query = requests_query.filter(func.date(Request.created_at) <= dt.date())
        except ValueError:
            pass
    if search_desc:
        requests_query = requests_query.filter(Request.description.ilike(f'%{search_desc}%'))
    requests = requests_query.order_by(Request.created_at.desc()).all()
    contracts = Contract.query.filter_by(client_id=client_id).all()
    photos = Media.query.filter_by(client_id=client_id).all()
    payments = Payment.query.filter_by(client_id=client_id).all()
    materials = db.session.query(Nomenclature.name, Nomenclature.price, Request.description).select_from(Nomenclature).join(Request, Nomenclature.id == Request.id).filter(Request.client_id == client_id).all()
    equipment = Equipment.query.filter_by(client_id=client_id).all()
    equipment_templates = EquipmentTemplate.query.filter(
        (EquipmentTemplate.client_id.is_(None)) | (EquipmentTemplate.client_id == client_id)
    ).all()
    now_date = date.today()
    return render_template('clients/detail.html', client=client, requests=requests, contracts=contracts,
                           photos=photos, payments=payments, materials=materials, equipment=equipment,
                           equipment_templates=equipment_templates, now_date=now_date,
                           req_type=req_type, date_from=date_from, date_to=date_to, search_desc=search_desc)


@clients_bp.route('/detail/<int:client_id>/contract/add', methods=['POST'])
@login_required
def add_contract(client_id):
    client = Client.query.get_or_404(client_id)
    contract_type = request.form.get('contract_type', '').strip()
    total_price = request.form.get('total_price')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    if not contract_type:
        flash('Укажите тип договора', 'error')
        return redirect(url_for('clients.client_detail', client_id=client_id) + '#tab-contracts')
    try:
        total_price = float(total_price) if total_price else 0
    except (ValueError, TypeError):
        total_price = 0
    if not start_date_str or not end_date_str:
        flash('Укажите даты начала и окончания', 'error')
        return redirect(url_for('clients.client_detail', client_id=client_id) + '#tab-contracts')
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    except ValueError:
        flash('Неверный формат дат', 'error')
        return redirect(url_for('clients.client_detail', client_id=client_id) + '#tab-contracts')
    contract = Contract(
        client_id=client_id,
        contract_type=contract_type,
        total_price=total_price,
        start_date=start_date,
        end_date=end_date
    )
    db.session.add(contract)
    db.session.commit()
    log.info(f'Договор добавлен для клиента {client_id}')
    flash('Договор успешно добавлен', 'success')
    return redirect(url_for('clients.client_detail', client_id=client_id))


@clients_bp.route('/contract/<int:contract_id>/print')
@login_required
def print_contract(contract_id):
    from app.utils.pdf_generator import generate_contract_pdf
    contract = Contract.query.get_or_404(contract_id)
    client = contract.client
    pdf_bytes = generate_contract_pdf(contract, client)
    if pdf_bytes:
        return send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'contract_{contract.id}.pdf'
        )
    flash('Ошибка генерации PDF. Установите WeasyPrint: pip install weasyprint', 'error')
    return redirect(url_for('clients.client_detail', client_id=client.id))

@clients_bp.route('/detail/<int:client_id>/equipment/add', methods=['POST'])
@login_required
def add_equipment_modal(client_id):
    client = Client.query.get_or_404(client_id)
    template_id = request.form.get('template_id', type=int)
    serial_number = request.form.get('serial_number', '').strip()
    eq_type = request.form.get('type', '').strip()
    brand = request.form.get('brand', '').strip()
    model = request.form.get('model', '').strip()
    power_val = request.form.get('power')
    production_year = request.form.get('production_year', type=int)
    contract_id = request.form.get('contract_id', type=int)
    if template_id:
        template = EquipmentTemplate.query.get(template_id)
        if template:
            eq_type = eq_type or template.type or ''
            brand = brand or (template.brand or '')
            model = model or (template.model or '')
            power_val = power_val or (str(template.power) if template.power else '')
            production_year = production_year or template.production_year
    if not serial_number:
        serial_number = f'AUTO-{client_id}-{Equipment.query.filter_by(client_id=client_id).count() + 1}'
    if not eq_type:
        eq_type = 'Оборудование'
    try:
        power = float(power_val) if power_val else None
    except (ValueError, TypeError):
        power = None
    equipment = Equipment(
        client_id=client_id,
        serial_number=serial_number,
        type=eq_type,
        brand=brand or None,
        model=model or None,
        power=power,
        production_year=production_year,
        contract_id=contract_id if contract_id else None
    )
    db.session.add(equipment)
    db.session.commit()
    log.info(f'Оборудование добавлено для клиента {client_id}')
    flash('Оборудование добавлено', 'success')
    return redirect(url_for('clients.client_detail', client_id=client_id))


@clients_bp.route('/map/<int:client_id>')
@login_required
def client_map(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template('clients/map.html', client=client)

@clients_bp.route('/export', methods=['GET'])
@login_required
def export():
    clients = Client.query.all()
    data = [
        {
            'id': c.id,
            'counterparty': c.counterparty,
            'full_name': c.full_name,
            'address': c.address,
            'phone': c.phone,
            'email': c.email
        } for c in clients
    ]
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', download_name='clients.xlsx')

@clients_bp.route('/import', methods=['POST'])
@login_required
def import_excel():
    if 'file' not in request.files:
        flash('Нет файла', 'error')
        return redirect(url_for('clients.clients'))
    file = request.files['file']
    if file.filename.endswith('.xlsx'):
        try:
            df = pd.read_excel(file)
            # Переименовать столбцы для поддержки русских заголовков
            column_mapping = {
                'ID': 'id',  # Игнорируем ID, не используем его
                'Контрагент': 'counterparty',
                'ФИО': 'full_name',
                'Адрес': 'address',
                'Телефон': 'phone',
                'Email': 'email',
                'Latitude': 'latitude',
                'Longitude': 'longitude',
                'Дата создания': 'created_at'
            }
            df.rename(columns=column_mapping, inplace=True)

            def get_value(row, key):
                val = row.get(key, None)
                if pd.isna(val):
                    return None
                return val

            for _, row in df.iterrows():
                counterparty = get_value(row, 'counterparty') or 'Не указано'
                full_name = get_value(row, 'full_name')  # Optional
                address = get_value(row, 'address') or 'Не указано'
                phone = get_value(row, 'phone') or 'Не указано'
                if phone is not None:
                    phone = str(phone)

                email = get_value(row, 'email')

                latitude_val = get_value(row, 'latitude')
                latitude = None
                if latitude_val is not None:
                    try:
                        latitude = float(latitude_val)
                    except ValueError:
                        flash(f'Неверное значение latitude: {latitude_val}', 'warning')
                        latitude = None

                longitude_val = get_value(row, 'longitude')
                longitude = None
                if longitude_val is not None:
                    try:
                        longitude = float(longitude_val)
                    except ValueError:
                        flash(f'Неверное значение longitude: {longitude_val}', 'warning')
                        longitude = None

                # Проверка на дубликат только если оба phone и address совпадают
                existing_client = Client.query.filter((Client.phone == phone) & (Client.address == address)).first()
                if existing_client:
                    flash(f'Клиент с телефоном {phone} и адресом {address} уже существует. Пропускаем.', 'warning')
                    continue

                client = Client(
                    counterparty=counterparty,
                    full_name=full_name,
                    address=address,
                    phone=phone,
                    email=email,
                    latitude=latitude,
                    longitude=longitude
                )
                db.session.add(client)
            db.session.commit()
            log.info('Импорт успешен')
            flash('Импорт завершён', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка импорта: {str(e)}', 'error')
    else:
        flash('Только .xlsx файлы', 'error')
    return redirect(url_for('clients.clients'))

@clients_bp.route('/update_coords/<int:client_id>', methods=['POST'])
@login_required
def update_coords(client_id):
    client = Client.query.get_or_404(client_id)
    data = request.json
    client.latitude = data['lat']
    client.longitude = data['long']
    db.session.commit()
    log.info(f'Координаты обновлены для клиента ID {client_id} via Ajax')
    return jsonify({'status': 'ok'}), 200