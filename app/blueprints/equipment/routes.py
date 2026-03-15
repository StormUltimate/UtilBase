# Path: app/blueprints/equipment/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required
from app.extensions import db
from app.models.all_models import Equipment, EquipmentTemplate, Client
from .forms import EquipmentForm, EquipmentTemplateForm, ImportForm
from app.config import Config
import os
from werkzeug.utils import secure_filename
import pandas as pd
from fuzzywuzzy import fuzz
from sqlalchemy.exc import SQLAlchemyError
from datetime import date
from io import BytesIO
from . import equipment_bp

@equipment_bp.route('/')
@login_required
def index():
    return redirect(url_for('equipment.list_equipment'))

@equipment_bp.route('/list')
@login_required
def list_equipment():
    """
    Общая вкладка оборудования:
    - показывает всё оборудование на обслуживании,
      с привязкой к клиентам/организациям (если есть client_id)
    - без иерархии, плоский список
    - фильтры по типу, бренду, модели, мощности и текстовому поиску
    """
    type_filter = request.args.get('type', '')
    brand_filter = request.args.get('brand', '')
    model_filter = request.args.get('model', '')
    power_filter = request.args.get('power', '')
    search_q = request.args.get('search', '').strip()

    query = Equipment.query.outerjoin(Client, Equipment.client_id == Client.id)

    if type_filter:
        query = query.filter(Equipment.type == type_filter)
    if brand_filter:
        query = query.filter(Equipment.brand == brand_filter)
    if model_filter:
        query = query.filter(Equipment.model == model_filter)
    if power_filter:
        # power - числовое поле, фильтруем по строковому вводу, если возможно преобразовать
        try:
            power_val = float(power_filter)
            query = query.filter(Equipment.power == power_val)
        except ValueError:
            pass

    if search_q:
        like = f"%{search_q}%"
        query = query.filter(
            (Equipment.type.ilike(like)) |
            (Equipment.brand.ilike(like)) |
            (Equipment.model.ilike(like)) |
            (Equipment.serial_number.ilike(like)) |
            (Client.full_name.ilike(like)) |
            (Client.address.ilike(like))
        )

    equipments = query.order_by(Equipment.type, Equipment.brand, Equipment.model).all()

    types = [t[0] for t in db.session.query(Equipment.type.distinct()).all() if t[0]]
    brands = [b[0] for b in db.session.query(Equipment.brand.distinct()).all() if b[0]]
    models = [m[0] for m in db.session.query(Equipment.model.distinct()).all() if m[0]]
    powers = [p[0] for p in db.session.query(Equipment.power.distinct()).all() if p[0] is not None]

    return render_template(
        'equipment/list.html',
        equipments=equipments,
        client=None,
        types=types,
        brands=brands,
        models=models,
        powers=powers,
        type_filter=type_filter,
        brand_filter=brand_filter,
        model_filter=model_filter,
        power_filter=power_filter,
        search_q=search_q,
    )

@equipment_bp.route('/client/<int:client_id>/list')
@login_required
def client_equipment_list(client_id):
    client = Client.query.get_or_404(client_id)
    type_filter = request.args.get('type', '')
    brand_filter = request.args.get('brand', '')
    model_filter = request.args.get('model', '')
    power_filter = request.args.get('power', '')
    search_q = request.args.get('search', '').strip()

    query = Equipment.query.filter_by(client_id=client_id)

    if type_filter:
        query = query.filter(Equipment.type == type_filter)
    if brand_filter:
        query = query.filter(Equipment.brand == brand_filter)
    if model_filter:
        query = query.filter(Equipment.model == model_filter)
    if power_filter:
        try:
            power_val = float(power_filter)
            query = query.filter(Equipment.power == power_val)
        except ValueError:
            pass
    if search_q:
        like = f"%{search_q}%"
        query = query.filter(
            (Equipment.type.ilike(like)) |
            (Equipment.brand.ilike(like)) |
            (Equipment.model.ilike(like)) |
            (Equipment.serial_number.ilike(like))
        )

    equipments = query.order_by(Equipment.type, Equipment.brand, Equipment.model).all()

    types = [t[0] for t in db.session.query(Equipment.type.distinct()).all() if t[0]]
    brands = [b[0] for b in db.session.query(Equipment.brand.distinct()).all() if b[0]]
    models = [m[0] for m in db.session.query(Equipment.model.distinct()).all() if m[0]]
    powers = [p[0] for p in db.session.query(Equipment.power.distinct()).all() if p[0] is not None]

    return render_template(
        'equipment/list.html',
        equipments=equipments,
        client=client,
        types=types,
        brands=brands,
        models=models,
        powers=powers,
        type_filter=type_filter,
        brand_filter=brand_filter,
        model_filter=model_filter,
        power_filter=power_filter,
        search_q=search_q,
    )

@equipment_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_equipment():
    form = EquipmentForm()
    form.parent_id.choices = [(0, 'Нет')] + [(e.id, f"{e.type} {e.brand or ''} {e.model or ''} ({e.serial_number})") for e in Equipment.query.all()]
    if form.validate_on_submit():
        try:
            photo_path = None
            if form.photo_path.data:
                filename = secure_filename(form.photo_path.data.filename)
                photo_path = os.path.join(Config.MEDIA_DIR, filename)
                form.photo_path.data.save(photo_path)
            document_path = None
            if form.document_path.data:
                filename = secure_filename(form.document_path.data.filename)
                document_path = os.path.join(Config.MEDIA_DIR, filename)
                form.document_path.data.save(document_path)
            equipment = Equipment(
                serial_number=form.serial_number.data,
                type=form.type.data,
                kind=form.kind.data,
                brand=form.brand.data,
                model=form.model.data,
                power=form.power.data,
                depth=form.depth.data,
                height=form.height.data,
                width=form.width.data,
                installation_type=form.installation_type.data,
                production_year=form.production_year.data,
                service_interval=form.service_interval.data,
                service_life=form.service_life.data,
                service_price=form.service_price.data,
                last_service_date=form.last_service_date.data,
                next_service_date=form.next_service_date.data,
                warranty_start_date=form.warranty_start_date.data,
                warranty_end_date=form.warranty_end_date.data,
                warranty_conditions=form.warranty_conditions.data,
                photo_path=photo_path,
                document_path=document_path,
                parent_id=form.parent_id.data if form.parent_id.data != 0 else None,
                latitude=form.latitude.data,
                longitude=form.longitude.data
            )
            db.session.add(equipment)
            db.session.commit()
            flash('Оборудование добавлено.', 'success')
            return redirect(url_for('equipment.list_equipment'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    return render_template('equipment/add.html', form=form)

@equipment_bp.route('/client/<int:client_id>/add', methods=['GET', 'POST'])
@login_required
def add_client_equipment(client_id):
    client = Client.query.get_or_404(client_id)
    form = EquipmentForm()
    form.parent_id.choices = [(0, 'Нет')] + [(e.id, f"{e.type} {e.brand or ''} {e.model or ''} ({e.serial_number})") for e in Equipment.query.filter_by(client_id=client_id).all()]
    if form.validate_on_submit():
        try:
            photo_path = None
            if form.photo_path.data:
                filename = secure_filename(form.photo_path.data.filename)
                photo_path = os.path.join(Config.MEDIA_DIR, filename)
                form.photo_path.data.save(photo_path)
            document_path = None
            if form.document_path.data:
                filename = secure_filename(form.document_path.data.filename)
                document_path = os.path.join(Config.MEDIA_DIR, filename)
                form.document_path.data.save(document_path)
            equipment = Equipment(
                client_id=client_id,
                serial_number=form.serial_number.data,
                type=form.type.data,
                kind=form.kind.data,
                brand=form.brand.data,
                model=form.model.data,
                power=form.power.data,
                depth=form.depth.data,
                height=form.height.data,
                width=form.width.data,
                installation_type=form.installation_type.data,
                production_year=form.production_year.data,
                service_interval=form.service_interval.data,
                service_life=form.service_life.data,
                service_price=form.service_price.data,
                last_service_date=form.last_service_date.data,
                next_service_date=form.next_service_date.data,
                warranty_start_date=form.warranty_start_date.data,
                warranty_end_date=form.warranty_end_date.data,
                warranty_conditions=form.warranty_conditions.data,
                photo_path=photo_path,
                document_path=document_path,
                parent_id=form.parent_id.data if form.parent_id.data != 0 else None,
                latitude=form.latitude.data,
                longitude=form.longitude.data
            )
            db.session.add(equipment)
            db.session.commit()
            flash('Оборудование добавлено.', 'success')
            return redirect(url_for('equipment.client_passport', client_id=client_id))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    return render_template('equipment/add.html', client=client, form=form)

@equipment_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_equipment(id):
    equipment = Equipment.query.get_or_404(id)
    form = EquipmentForm(obj=equipment)
    form.parent_id.choices = [(0, 'Нет')] + [(e.id, f"{e.type} {e.brand or ''} {e.model or ''} ({e.serial_number})") for e in Equipment.query.filter(Equipment.id != id).all()]
    if form.validate_on_submit():
        try:
            if form.photo_path.data:
                filename = secure_filename(form.photo_path.data.filename)
                photo_path = os.path.join(Config.MEDIA_DIR, filename)
                form.photo_path.data.save(photo_path)
                equipment.photo_path = photo_path
            if form.document_path.data:
                filename = secure_filename(form.document_path.data.filename)
                document_path = os.path.join(Config.MEDIA_DIR, filename)
                form.document_path.data.save(document_path)
                equipment.document_path = document_path
            equipment.serial_number = form.serial_number.data
            equipment.type = form.type.data
            equipment.kind = form.kind.data
            equipment.brand = form.brand.data
            equipment.model = form.model.data
            equipment.power = form.power.data
            equipment.depth = form.depth.data
            equipment.height = form.height.data
            equipment.width = form.width.data
            equipment.installation_type = form.installation_type.data
            equipment.production_year = form.production_year.data
            equipment.service_interval = form.service_interval.data
            equipment.service_life = form.service_life.data
            equipment.service_price = form.service_price.data
            equipment.last_service_date = form.last_service_date.data
            equipment.next_service_date = form.next_service_date.data
            equipment.warranty_start_date = form.warranty_start_date.data
            equipment.warranty_end_date = form.warranty_end_date.data
            equipment.warranty_conditions = form.warranty_conditions.data
            equipment.parent_id = form.parent_id.data if form.parent_id.data != 0 else None
            equipment.latitude = form.latitude.data
            equipment.longitude = form.longitude.data
            db.session.commit()
            flash('Оборудование обновлено.', 'success')
            return redirect(url_for('equipment.list_equipment'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    return render_template('equipment/edit.html', form=form, equipment=equipment)

@equipment_bp.route('/client/<int:client_id>/maintenance', methods=['GET'])
@login_required
def client_maintenance(client_id):
    client = Client.query.get_or_404(client_id)
    equipments = Equipment.query.filter_by(client_id=client_id).all()
    return render_template('equipment/maintenance.html', client=client, equipments=equipments)

@equipment_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_equipment(id):
    equipment = Equipment.query.get_or_404(id)
    try:
        if equipment.photo_path and os.path.exists(equipment.photo_path):
            os.remove(equipment.photo_path)
        if equipment.document_path and os.path.exists(equipment.document_path):
            os.remove(equipment.document_path)
        db.session.delete(equipment)
        db.session.commit()
        flash('Оборудование удалено.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'danger')
    return redirect(url_for('equipment.list_equipment'))

@equipment_bp.route('/templates/list')
@login_required
def templates_list():
    templates = EquipmentTemplate.query.all()
    return render_template('equipment/templates.html', templates=templates)

@equipment_bp.route('/templates/add', methods=['GET', 'POST'])
@login_required
def add_template():
    form = EquipmentTemplateForm()
    if form.validate_on_submit():
        try:
            photo_path = None
            if form.photo_path.data:
                filename = secure_filename(form.photo_path.data.filename)
                photo_path = os.path.join(Config.MEDIA_DIR, filename)
                form.photo_path.data.save(photo_path)
            document_path = None
            if form.document_path.data:
                filename = secure_filename(form.document_path.data.filename)
                document_path = os.path.join(Config.MEDIA_DIR, filename)
                form.document_path.data.save(document_path)
            template = EquipmentTemplate(
                type=form.type.data,
                kind=form.kind.data,
                brand=form.brand.data,
                model=form.model.data,
                power=form.power.data,
                depth=form.depth.data,
                height=form.height.data,
                width=form.width.data,
                installation_type=form.installation_type.data,
                production_year=form.production_year.data,
                service_interval=form.service_interval.data,
                service_life=form.service_life.data,
                service_price=form.service_price.data,
                photo_path=photo_path,
                document_path=document_path
            )
            db.session.add(template)
            db.session.commit()
            flash('Шаблон добавлен.', 'success')
            return redirect(url_for('equipment.templates_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    return render_template('equipment/add_template.html', form=form)

@equipment_bp.route('/templates/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_template(id):
    template = EquipmentTemplate.query.get_or_404(id)
    form = EquipmentTemplateForm(obj=template)
    if form.validate_on_submit():
        try:
            if form.photo_path.data:
                filename = secure_filename(form.photo_path.data.filename)
                photo_path = os.path.join(Config.MEDIA_DIR, filename)
                form.photo_path.data.save(photo_path)
                template.photo_path = photo_path
            if form.document_path.data:
                filename = secure_filename(form.document_path.data.filename)
                document_path = os.path.join(Config.MEDIA_DIR, filename)
                form.document_path.data.save(document_path)
                template.document_path = document_path
            template.type = form.type.data
            template.kind = form.kind.data
            template.brand = form.brand.data
            template.model = form.model.data
            template.power = form.power.data
            template.depth = form.depth.data
            template.height = form.height.data
            template.width = form.width.data
            template.installation_type = form.installation_type.data
            template.production_year = form.production_year.data
            template.service_interval = form.service_interval.data
            template.service_life = form.service_life.data
            template.service_price = form.service_price.data
            db.session.commit()
            flash('Шаблон обновлен.', 'success')
            return redirect(url_for('equipment.templates_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    return render_template('equipment/edit_template.html', form=form, template=template)

@equipment_bp.route('/templates/delete/<int:id>', methods=['POST'])
@login_required
def delete_template(id):
    template = EquipmentTemplate.query.get_or_404(id)
    try:
        if template.photo_path and os.path.exists(template.photo_path):
            os.remove(template.photo_path)
        if template.document_path and os.path.exists(template.document_path):
            os.remove(template.document_path)
        db.session.delete(template)
        db.session.commit()
        flash('Шаблон удален.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'danger')
    return redirect(url_for('equipment.templates_list'))

@equipment_bp.route('/templates/search')
@login_required
def search_templates():
    q = request.args.get('q', '')
    templates = EquipmentTemplate.query.all()
    results = []
    for t in templates:
        scores = [fuzz.partial_ratio(q, field) for field in [t.type or '', t.brand or '', t.model or '']]
        score = max(scores)
        if score > 80:
            results.append({
                'id': t.id,
                'label': f"{t.type} {t.brand or ''} {t.model or ''} ({score}%)",
                'data': {
                    'type': t.type,
                    'kind': t.kind or '',
                    'brand': t.brand or '',
                    'model': t.model or '',
                    'power': t.power or '',
                    'depth': t.depth,
                    'height': t.height,
                    'width': t.width,
                    'installation_type': t.installation_type or '',
                    'production_year': t.production_year,
                    'service_interval': t.service_interval,
                    'service_life': t.service_life,
                    'service_price': t.service_price,
                    'photo_path': t.photo_path or '',
                    'document_path': t.document_path or ''
                },
                'score': score
            })
    results.sort(key=lambda x: -x['score'])
    return jsonify(results[:10])

@equipment_bp.route('/templates/import', methods=['GET', 'POST'])
@login_required
def import_templates():
    form = ImportForm()
    if form.validate_on_submit():
        file = form.file.data
        if file and file.filename.endswith('.xlsx'):
            try:
                df = pd.read_excel(file)
                for _, row in df.iterrows():
                    template = EquipmentTemplate(
                        type=row.get('type'),
                        kind=row.get('kind'),
                        brand=row.get('brand'),
                        model=row.get('model'),
                        power=row.get('power'),
                        depth=row.get('depth'),
                        height=row.get('height'),
                        width=row.get('width'),
                        installation_type=row.get('installation_type'),
                        production_year=row.get('production_year'),
                        service_interval=row.get('service_interval'),
                        service_life=row.get('service_life'),
                        service_price=row.get('service_price'),
                        photo_path=row.get('photo_path'),
                        document_path=row.get('document_path')
                    )
                    db.session.add(template)
                db.session.commit()
                flash('Шаблоны импортированы.', 'success')
                return redirect(url_for('equipment.templates_list'))
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка: {str(e)}', 'danger')
    return render_template('equipment/import.html', form=form)

@equipment_bp.route('/hierarchy')
@login_required
def hierarchy():
    tree = []
    def build_tree(equipments, level=0):
        for e in equipments:
            tree.append((e, level))
            build_tree(e.sub_equipments.all(), level + 1)
    top_level = Equipment.query.filter_by(parent_id=None).all()
    build_tree(top_level)
    return render_template('equipment/hierarchy.html', tree=tree)

@equipment_bp.route('/client/<int:client_id>/hierarchy')
@login_required
def client_hierarchy(client_id):
    client = Client.query.get_or_404(client_id)
    tree = []
    def build_tree(equipments, level=0):
        for e in equipments:
            tree.append((e, level))
            build_tree(e.sub_equipments.all(), level + 1)
    top_level = Equipment.query.filter_by(client_id=client_id, parent_id=None).all()
    build_tree(top_level)
    return render_template('equipment/hierarchy.html', client=client, tree=tree)

@equipment_bp.route('/client/<int:client_id>/passport', methods=['GET', 'POST'])
@login_required
def client_passport(client_id):
    client = Client.query.get_or_404(client_id)
    form = EquipmentForm()
    form.parent_id.choices = [(0, 'Нет')] + [(e.id, f"{e.type} {e.brand or ''} {e.model or ''} ({e.serial_number})") for e in Equipment.query.filter_by(client_id=client_id).all()]
    
    if form.validate_on_submit():
        try:
            photo_path = None
            if form.photo_path.data:
                filename = secure_filename(form.photo_path.data.filename)
                photo_path = os.path.join(Config.MEDIA_DIR, filename)
                form.photo_path.data.save(photo_path)
            document_path = None
            if form.document_path.data:
                filename = secure_filename(form.document_path.data.filename)
                document_path = os.path.join(Config.MEDIA_DIR, filename)
                form.document_path.data.save(document_path)
            equipment = Equipment(
                client_id=client_id,
                serial_number=form.serial_number.data,
                type=form.type.data,
                kind=form.kind.data,
                brand=form.brand.data,
                model=form.model.data,
                power=form.power.data,
                depth=form.depth.data,
                height=form.height.data,
                width=form.width.data,
                installation_type=form.installation_type.data,
                production_year=form.production_year.data,
                service_interval=form.service_interval.data,
                service_life=form.service_life.data,
                service_price=form.service_price.data,
                last_service_date=form.last_service_date.data,
                next_service_date=form.next_service_date.data,
                warranty_start_date=form.warranty_start_date.data,
                warranty_end_date=form.warranty_end_date.data,
                warranty_conditions=form.warranty_conditions.data,
                photo_path=photo_path,
                document_path=document_path,
                parent_id=form.parent_id.data if form.parent_id.data != 0 else None,
                latitude=form.latitude.data,
                longitude=form.longitude.data
            )
            db.session.add(equipment)
            db.session.commit()
            flash('Оборудование добавлено в паспорт клиента.', 'success')
            return redirect(url_for('equipment.client_passport', client_id=client_id))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    
    tree = []
    def build_tree(equipments, level=0):
        for e in equipments:
            tree.append((e, level))
            build_tree(e.sub_equipments.all(), level + 1)
    top_level = Equipment.query.filter_by(client_id=client_id, parent_id=None).all()
    build_tree(top_level)
    
    return render_template('equipment/client_passport.html', client=client, form=form, tree=tree)

@equipment_bp.route('/api/equipment/search', methods=['GET'])
@login_required
def api_equipment_search():
    q = request.args.get('q', '')
    client_id = request.args.get('client_id', type=int)
    type_filter = request.args.get('type', '')
    equipments = Equipment.query
    if client_id:
        equipments = equipments.filter_by(client_id=client_id)
    if type_filter:
        equipments = equipments.filter_by(type=type_filter)
    if q:
        equipments = equipments.filter(
            (Equipment.serial_number.ilike(f'%{q}%')) |
            (Equipment.type.ilike(f'%{q}%')) |
            (Equipment.brand.ilike(f'%{q}%')) |
            (Equipment.model.ilike(f'%{q}%'))
        )
    results = [{
        'id': e.id,
        'type': e.type,
        'serial_number': e.serial_number,
        'brand': e.brand or '',
        'model': e.model or '',
        'latitude': e.latitude or e.client.latitude if e.client else None,
        'longitude': e.longitude or e.client.longitude if e.client else None,
        'status': 'red' if e.next_service_date and e.next_service_date < date.today() else 'green'
    } for e in equipments.all()]
    return jsonify(results)

@equipment_bp.route('/annual_volume')
@login_required
def annual_volume():
    total_hours = sum(eq.annual_service_time() for eq in Equipment.query.all())
    return render_template('equipment/annual_volume.html', total=total_hours)

@equipment_bp.route('/export_excel')
@login_required
def export_excel():
    type_filter = request.args.get('type', '')
    power_filter = request.args.get('power', '')
    service_interval_filter = request.args.get('service_interval', '')
    production_year_filter = request.args.get('production_year', '')
    query = Equipment.query
    if type_filter:
        query = query.filter_by(type=type_filter)
    if power_filter:
        query = query.filter_by(power=power_filter)
    if service_interval_filter:
        query = query.filter_by(service_interval=service_interval_filter)
    if production_year_filter:
        query = query.filter_by(production_year=production_year_filter)
    equipments = query.all()
    data = [
        {
            'ID': e.id,
            'Client ID': e.client_id,
            'Parent ID': e.parent_id,
            'Serial Number': e.serial_number,
            'Type': e.type,
            'Kind': e.kind,
            'Brand': e.brand,
            'Model': e.model,
            'Power': e.power,
            'Depth': e.depth,
            'Height': e.height,
            'Width': e.width,
            'Installation Type': e.installation_type,
            'Production Year': e.production_year,
            'Service Interval': e.service_interval,
            'Service Life': e.service_life,
            'Service Price': e.service_price,
            'Last Service Date': e.last_service_date,
            'Next Service Date': e.next_service_date,
            'Warranty Start Date': e.warranty_start_date,
            'Warranty End Date': e.warranty_end_date,
            'Warranty Conditions': e.warranty_conditions,
            'Photo Path': e.photo_path,
            'Document Path': e.document_path,
            'Latitude': e.latitude,
            'Longitude': e.longitude,
            'Created At': e.created_at,
            'Updated At': e.updated_at
        } for e in equipments
    ]
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Equipment', index=False)
    output.seek(0)
    return send_file(output, download_name='equipment.xlsx', as_attachment=True)

@equipment_bp.route('/templates/export')
@login_required
def templates_export():
    templates = EquipmentTemplate.query.all()
    data = [
        {
            'ID': t.id,
            'Type': t.type,
            'Kind': t.kind,
            'Brand': t.brand,
            'Model': t.model,
            'Power': t.power,
            'Depth': t.depth,
            'Height': t.height,
            'Width': t.width,
            'Installation Type': t.installation_type,
            'Production Year': t.production_year,
            'Service Interval': t.service_interval,
            'Service Life': t.service_life,
            'Service Price': t.service_price,
            'Photo Path': t.photo_path,
            'Document Path': t.document_path
        } for t in templates
    ]
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Templates', index=False)
    output.seek(0)
    return send_file(output, download_name='templates.xlsx', as_attachment=True)