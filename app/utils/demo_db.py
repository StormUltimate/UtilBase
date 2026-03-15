# Path: app/utils/demo_db.py
"""Создание и удаление тестовых (демо) данных в БД."""
import os
from datetime import datetime, date, timedelta, time

from app.extensions import db
from app.models.all_models import (
    Client,
    Contract,
    Request,
    Worker,
    Media,
    request_workers,
    WorkOrder,
    Equipment,
)
from app.models.all_models import ServiceType, RequestStatus, RequestMode


DEMO_CLIENT_PREFIX = "Демо Клиент"
DEMO_WORKER_PREFIX = "Демо "
DEMO_REQUEST_PREFIX = "DEMO:"
DEMO_MEDIA_DESCRIPTION_PREFIX = "Демо: "

# Путь-заглушка для демо-фото (файла нет на диске — при просмотре будет редирект «Файл не найден»)
DEMO_MEDIA_PLACEHOLDER_PATH = "uploads/demo/placeholder.png"


def _ensure_demo_placeholder_dir(app):
    """Создаёт каталог для демо-медиа при необходимости."""
    if app is None:
        return
    demo_dir = os.path.join(app.root_path, "static", "uploads", "demo")
    try:
        os.makedirs(demo_dir, exist_ok=True)
        placeholder = os.path.join(demo_dir, "placeholder.png")
        if not os.path.exists(placeholder):
            with open(placeholder, "wb") as f:
                f.write(b"")
    except OSError:
        pass


def create_demo_data(app=None):
    """
    Создаёт демо-данные: клиенты, договоры, заявки (часть закрытых),
    исполнители, пустые записи медиа (без файлов в папке).
    """
    _ensure_demo_placeholder_dir(app)

    # 1) Демо-исполнители
    existing_workers = Worker.query.filter(Worker.full_name.like(f"{DEMO_WORKER_PREFIX}%")).all()
    if not existing_workers:
        for i, role in enumerate(["master", "master", "engineer"], 1):
            name = f"{DEMO_WORKER_PREFIX}мастер {i}" if role != "engineer" else f"{DEMO_WORKER_PREFIX}инженер"
            w = Worker(full_name=name, phone=f"+7 900 000-00-0{i}", role=role)
            db.session.add(w)
        db.session.flush()
        demo_workers = Worker.query.filter(Worker.full_name.like(f"{DEMO_WORKER_PREFIX}%")).all()
    else:
        demo_workers = existing_workers

    # 2) Демо-клиенты
    existing_clients = Client.query.filter(Client.full_name.like(f"{DEMO_CLIENT_PREFIX}%")).all()
    if existing_clients:
        demo_clients = existing_clients
    else:
        demo_clients = []
        for i in range(1, 4):
            c = Client(
                full_name=f"{DEMO_CLIENT_PREFIX} {i}",
                address=f"Демо адрес, д. {i}",
                phone=f"+7 900 111-11-1{i}",
                email=f"demo{i}@example.local",
                counterparty="Демо",
            )
            db.session.add(c)
            demo_clients.append(c)
        db.session.flush()

    # 3) Договоры у демо-клиентов
    for client in demo_clients:
        existing = Contract.query.filter_by(client_id=client.id).first()
        if not existing:
            for j, ctype in enumerate(["комплексный", "отопление"], 1):
                contract = Contract(
                    client_id=client.id,
                    contract_type=ctype,
                    total_price=10000.0 * j,
                    start_date=datetime.now() - timedelta(days=365),
                    end_date=datetime.now() + timedelta(days=365),
                )
                db.session.add(contract)
    db.session.flush()

    # 4) Заявки: часть закрытых, часть в работе
    today = date.today()
    start_day = today - timedelta(days=14)
    end_day = today + timedelta(days=14)
    req_num = 1
    for client in demo_clients:
        contracts = Contract.query.filter_by(client_id=client.id).all()
        contract = contracts[0] if contracts else None
        for day_offset in range(-7, 8):
            planned_date = today + timedelta(days=day_offset)
            if planned_date < start_day or planned_date > end_day:
                continue
            for slot in (0, 1):
                status = RequestStatus.closed if day_offset < 0 else RequestStatus.assigned
                if day_offset == 0 and slot == 1:
                    status = RequestStatus.pending
                planned_start = datetime.combine(planned_date, time(9 + slot * 3, 0))
                planned_end = planned_start + timedelta(hours=2)
                service_type = ServiceType.emergency if req_num % 3 == 1 else ServiceType.standard
                r = Request(
                    client_id=client.id,
                    contract_id=contract.id if contract else None,
                    equipment_id=None,
                    created_by_user_id=None,
                    updated_by_user_id=None,
                    request_number=f"DEMO-{req_num:04d}",
                    description=f"{DEMO_REQUEST_PREFIX} Заявка #{req_num}",
                    service_type=service_type,
                    urgent_price=0,
                    total_price=0,
                    estimated_time=2,
                    planned_date=planned_date,
                    planned_start_time=planned_start,
                    planned_end_time=planned_end,
                    status=status,
                    mode=RequestMode.normal,
                    workers_count=1,
                )
                db.session.add(r)
                db.session.flush()
                if demo_workers and r.id:
                    w = demo_workers[req_num % len(demo_workers)]
                    db.session.execute(
                        request_workers.insert().values(request_id=r.id, worker_id=w.id)
                    )
                req_num += 1
    db.session.flush()

    # 5) Пустые записи медиа (без реальных файлов — путь-заглушка)
    for client in demo_clients[:2]:
        for idx in range(1, 3):
            m = Media(
                client_id=client.id,
                file_path=DEMO_MEDIA_PLACEHOLDER_PATH,
                file_type="photo",
                description=f"{DEMO_MEDIA_DESCRIPTION_PREFIX} фото {idx}",
            )
            db.session.add(m)
    db.session.commit()
    return True


def delete_demo_data():
    """Удаляет все демо-данные: клиенты, договоры, заявки, исполнители, демо-медиа."""
    from sqlalchemy import text, or_

    demo_clients = Client.query.filter(Client.full_name.like(f"{DEMO_CLIENT_PREFIX}%")).all()
    demo_client_ids = [c.id for c in demo_clients]

    # Заявки: префикс DEMO: или клиент — демо
    demo_requests = Request.query.filter(
        or_(
            Request.description.like(f"{DEMO_REQUEST_PREFIX}%"),
            Request.client_id.in_(demo_client_ids),
        )
    ).all()
    demo_request_ids = [r.id for r in demo_requests]

    # Связь заявка–исполнитель
    if demo_request_ids:
        db.session.execute(
            text("DELETE FROM request_workers WHERE request_id = ANY(:ids)"),
            {"ids": demo_request_ids},
        )

    # Наряды по демо-заявкам
    if demo_request_ids:
        WorkOrder.query.filter(WorkOrder.request_id.in_(demo_request_ids)).delete(synchronize_session=False)

    # Заявки
    for r in demo_requests:
        db.session.delete(r)

    # Медиа демо
    demo_media = Media.query.filter(
        or_(
            Media.description.like(f"{DEMO_MEDIA_DESCRIPTION_PREFIX}%"),
            Media.client_id.in_(demo_client_ids),
        )
    ).all()
    for m in demo_media:
        db.session.delete(m)

    if demo_client_ids:
        WorkOrder.query.filter(WorkOrder.client_id.in_(demo_client_ids)).delete(synchronize_session=False)
        Equipment.query.filter(Equipment.client_id.in_(demo_client_ids)).delete(synchronize_session=False)
        Contract.query.filter(Contract.client_id.in_(demo_client_ids)).delete(synchronize_session=False)

    for c in demo_clients:
        db.session.delete(c)

    Worker.query.filter(Worker.full_name.like(f"{DEMO_WORKER_PREFIX}%")).delete(synchronize_session=False)
    db.session.commit()
    return True
