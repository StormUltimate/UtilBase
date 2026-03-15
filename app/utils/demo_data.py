# Path: app/utils/demo_data.py
"""Фейковые данные для демо-режима (без БД)."""
from datetime import datetime, date
from types import SimpleNamespace


def get_demo_data():
    """Возвращает структуру данных для демо-страницы: клиент, договоры, оборудование, заявки, фото."""
    now = date.today()

    client = SimpleNamespace(
        id=1,
        full_name='Иванов Иван Иванович',
        phone='+7 (999) 123-45-67',
        email='ivanov@example.com',
        address='Московская обл., Одинцовский р-н, с. Зайцево, ул. Дачная, 15',
        representative_name='Иванов И.И.',
        representative_phone='+7 (999) 123-45-67',
        counterparty='Частное лицо',
        created_at=datetime(2024, 1, 15, 10, 0),
        latitude=55.7558,
        longitude=37.6173,
    )

    contracts = [
        SimpleNamespace(
            id=1,
            contract_type='комплексный',
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2025, 12, 31),
            total_price=45000,
        ),
        SimpleNamespace(
            id=2,
            contract_type='отопление',
            start_date=datetime(2023, 6, 1),
            end_date=datetime(2024, 5, 31),
            total_price=25000,
        ),
    ]

    equipment = [
        SimpleNamespace(
            id=1,
            brand='Buderus',
            model='Logamax U052',
            type='Котёл газовый',
            power=24.0,
            production_year=2020,
            serial_number='SN-2020-001',
            created_at=datetime(2024, 1, 20),
            contract_id=1,
            contract=SimpleNamespace(contract_type='комплексный', id=1),
        ),
        SimpleNamespace(
            id=2,
            brand='Grundfos',
            model='UPS 25-40',
            type='Циркуляционный насос',
            power=None,
            production_year=2019,
            serial_number='GR-2019-042',
            created_at=datetime(2024, 1, 20),
            contract_id=1,
            contract=SimpleNamespace(contract_type='комплексный', id=1),
        ),
    ]

    class ReqStatus:
        name = 'assigned'
        value = 'Назначена'

    requests = [
        SimpleNamespace(
            id=1,
            request_number='З-2024-001',
            type='аварийная',
            description='Нет горячей воды, котёл не включается',
            urgent_price=3500,
            total_price=3500,
            status=ReqStatus(),
            created_at=datetime(2024, 3, 10, 9, 0),
        ),
        SimpleNamespace(
            id=2,
            request_number='З-2024-002',
            type='ремонтная',
            description='Плановое обслуживание котла',
            urgent_price=None,
            total_price=1500,
            status=SimpleNamespace(name='closed', value='Закрыта'),
            created_at=datetime(2024, 2, 15, 14, 0),
        ),
    ]

    photos = [
        SimpleNamespace(
            id=1,
            file_type='photo',
            upload_date=datetime(2024, 3, 10, 10, 30),
            description='Котёл Buderus — общий вид',
        ),
        SimpleNamespace(
            id=2,
            file_type='photo',
            upload_date=datetime(2024, 2, 15, 15, 0),
            description='Замена фильтра',
        ),
    ]

    return {
        'client': client,
        'contracts': contracts,
        'equipment': equipment,
        'requests': requests,
        'photos': photos,
        'now_date': now,
        'equipment_templates': [],
    }
