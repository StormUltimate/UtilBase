# Path: app/blueprints/map/routes.py
from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models.all_models import Client, Equipment, Request
from app.blueprints.map.forms import MapFilterForm
from sqlalchemy import and_
from flask import current_app

map_bp = Blueprint('map', __name__, template_folder='templates')

@map_bp.route('/map', methods=['GET', 'POST'], strict_slashes=False)
@login_required
def map():
    form = MapFilterForm()
    markers = []
    
    if form.validate_on_submit():
        filter_type = form.filter_type.data
        client_search = form.client_search.data.strip() if form.client_search.data else ''
        request_search = form.request_search.data.strip() if form.request_search.data else ''
        
        # Клиенты
        clients_query = Client.query.filter(and_(Client.latitude.isnot(None), Client.longitude.isnot(None)))
        if client_search:
            like = f"%{client_search}%"
            clients_query = clients_query.filter(
                (Client.full_name.ilike(like)) |
                (Client.address.ilike(like)) |
                (Client.phone.ilike(like))
            )
        clients = clients_query.all()

        # Заявки (актуальные)
        requests_query = Request.query.filter(Request.status.in_(['pending', 'assigned', 'overdue']))
        if request_search:
            like_r = f"%{request_search}%"
            requests_query = requests_query.filter(
                (Request.request_number.ilike(like_r)) |
                (Request.description.ilike(like_r))
            )
        if client_search:
            like_c = f"%{client_search}%"
            requests_query = requests_query.join(Client, Client.id == Request.client_id, isouter=True).filter(
                (Client.full_name.ilike(like_c)) |
                (Client.address.ilike(like_c)) |
                (Client.phone.ilike(like_c))
            )
        requests = requests_query.all()
        seen_locations = set()

        if filter_type == 'clients':
            markers = [
                {
                    'lat': c.latitude,
                    'lon': c.longitude,
                    'popup': f'Клиент: {c.full_name or ""}'
                             f'{(" • " + c.address) if c.address else ""}'
                             f'{(" • " + c.phone) if c.phone else ""}'
                }
                for c in clients
            ]
        
        elif filter_type == 'requests':
            for req in requests:
                lat, lon, popup = None, None, None
                if req.client and req.client.latitude and req.client.longitude:
                    lat, lon = req.client.latitude, req.client.longitude
                    popup = f'Заявка #{req.id} для клиента {req.client.full_name}'
                elif req.equipment and req.equipment.latitude and req.equipment.longitude:
                    lat, lon = req.equipment.latitude, req.equipment.longitude
                    popup = f'Заявка #{req.id} для оборудования {req.equipment.type}'
                if lat and lon and (lat, lon) not in seen_locations:
                    markers.append({'lat': lat, 'lon': lon, 'popup': popup})
                    seen_locations.add((lat, lon))
        
        else:  # all: клиенты + заявки
            markers = [
                {
                    'lat': c.latitude,
                    'lon': c.longitude,
                    'popup': f'Клиент: {c.full_name or ""}'
                             f'{(" • " + c.address) if c.address else ""}'
                             f'{(" • " + c.phone) if c.phone else ""}'
                }
                for c in clients
            ]
            for req in requests:
                lat, lon, popup = None, None, None
                if req.client and req.client.latitude and req.client.longitude:
                    lat, lon = req.client.latitude, req.client.longitude
                    popup = f'Заявка #{req.id} для клиента {req.client.full_name}'
                elif req.equipment and req.equipment.latitude and req.equipment.longitude:
                    lat, lon = req.equipment.latitude, req.equipment.longitude
                    popup = f'Заявка #{req.id} для оборудования {req.equipment.type}'
                if lat and lon and (lat, lon) not in seen_locations:
                    markers.append({'lat': lat, 'lon': lon, 'popup': popup})
                    seen_locations.add((lat, lon))
    
    else:
        # Default: все клиенты без фильтра
        clients = Client.query.filter(and_(Client.latitude.isnot(None), Client.longitude.isnot(None))).all()
        markers = [
            {
                'lat': c.latitude,
                'lon': c.longitude,
                'popup': f'Клиент: {c.full_name or ""}'
                         f'{(" • " + c.address) if c.address else ""}'
                         f'{(" • " + c.phone) if c.phone else ""}'
            }
            for c in clients
        ]

    # Список клиентов для подсказок (ограничим по количеству) — преобразуем в словари для JSON
    clients_rows = Client.query.with_entities(
        Client.id,
        Client.full_name,
        Client.phone,
        Client.address,
        Client.latitude,
        Client.longitude
    ).limit(500).all()
    clients_for_search = [
        {
            'id': row[0],
            'full_name': row[1],
            'phone': row[2],
            'address': row[3],
            'latitude': float(row[4]) if row[4] is not None else None,
            'longitude': float(row[5]) if row[5] is not None else None,
        }
        for row in clients_rows
    ]
    
    yandex_api_key = current_app.config.get('YANDEX_API_KEY', 'your-yandex-api-key-here')
    
    return render_template(
        'map/map.html',
        form=form,
        markers=markers,
        yandex_api_key=yandex_api_key,
        clients_for_search=clients_for_search
    )

@map_bp.route('/client/<int:client_id>/map', methods=['GET', 'POST'], strict_slashes=False)
@login_required
def client_map(client_id):
    client = Client.query.get_or_404(client_id)
    form = MapFilterForm()
    markers = [{'lat': client.latitude, 'lon': client.longitude, 'popup': f'Клиент: {client.full_name}'}] if client.latitude and client.longitude else []
    
    equipments = Equipment.query.filter_by(client_id=client_id).all()
    markers += [{'lat': e.latitude, 'lon': e.longitude, 'popup': f'Оборудование: {e.type}'} for e in equipments if e.latitude and e.longitude]
    
    yandex_api_key = current_app.config.get('YANDEX_API_KEY', 'your-yandex-api-key-here')
    
    return render_template('map/map.html', client=client, form=form, markers=markers, yandex_api_key=yandex_api_key)