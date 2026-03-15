"""add demo workers and requests for calendar testing

Revision ID: d1e2f3g4h5i6
Revises: c3d4e5f6a7b8
Create Date: 2026-03-13

Эта миграция создаёт несколько демонстрационных исполнителей и заявок
на месяц назад и вперёд, чтобы проверить работу план‑графика.
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime, date, timedelta, time


revision = 'd1e2f3g4h5i6'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # --- Добавляем демо‑исполнителей ---
    workers_data = [
        {'full_name': 'Демо мастер 1', 'phone': '+7 900 000-00-01', 'role': 'master'},
        {'full_name': 'Демо мастер 2', 'phone': '+7 900 000-00-02', 'role': 'master'},
        {'full_name': 'Демо инженер', 'phone': '+7 900 000-00-03', 'role': 'engineer'},
    ]

    worker_ids = []
    for w in workers_data:
        res = bind.execute(
            sa.text(
                """
                INSERT INTO workers (full_name, phone, role, created_at)
                VALUES (:full_name, :phone, :role, :created_at)
                RETURNING id
                """
            ),
            {
                'full_name': w['full_name'],
                'phone': w['phone'],
                'role': w['role'],
                'created_at': datetime.utcnow(),
            },
        )
        new_id = res.scalar()
        if new_id is not None:
            worker_ids.append(new_id)

    if not worker_ids:
        # Если по какой‑то причине не удалось создать исполнителей, выходим
        return

    # --- Добавляем демо‑заявки на месяц назад и вперёд ---
    today = date.today()
    start_day = today - timedelta(days=30)
    end_day = today + timedelta(days=30)

    demo_prefix = 'DEMO: '
    current_number = 1

    while start_day <= end_day:
        # По 1–2 заявки в день
        for offset in (0, 1):
            planned_date = start_day
            planned_start = datetime.combine(planned_date, time(9 + offset * 3, 0))
            planned_end = planned_start + timedelta(hours=2)

            # Чередуем типы. В service_type пишем допустимые значения Enum: standard / warranty / emergency
            if current_number % 3 == 1:
                req_type = 'аварийная'
                status = 'pending'
                service_type = 'emergency'
            elif current_number % 3 == 2:
                req_type = 'ремонтная'
                status = 'assigned'
                service_type = 'standard'
            else:
                req_type = 'плановая'
                status = 'assigned'
                service_type = 'standard'

            desc = f"{demo_prefix}{req_type.capitalize()} работа #{current_number}"

            res_req = bind.execute(
                sa.text(
                    """
                    INSERT INTO requests (
                        client_id,
                        contract_id,
                        equipment_id,
                        created_by_user_id,
                        updated_by_user_id,
                        request_number,
                        description,
                        service_type,
                        urgent_price,
                        total_price,
                        estimated_time,
                        planned_date,
                        planned_start_time,
                        planned_end_time,
                        status,
                        mode,
                        workers_count,
                        created_at
                    ) VALUES (
                        NULL,
                        NULL,
                        NULL,
                        NULL,
                        NULL,
                        :request_number,
                        :description,
                        :service_type,
                        :urgent_price,
                        :total_price,
                        :estimated_time,
                        :planned_date,
                        :planned_start_time,
                        :planned_end_time,
                        :status,
                        :mode,
                        :workers_count,
                        :created_at
                    )
                    RETURNING id
                    """
                ),
                {
                    'request_number': f'DEMO-{current_number:04d}',
                    'description': desc,
                    'service_type': service_type,
                    'urgent_price': 0,
                    'total_price': 0,
                    'estimated_time': 2,
                    'planned_date': planned_date,
                    'planned_start_time': planned_start,
                    'planned_end_time': planned_end,
                    'status': status,
                    'mode': 'normal',
                    'workers_count': 1,
                    'created_at': datetime.utcnow(),
                },
            )
            req_id = res_req.scalar()

            # Привязываем 1–2 исполнителей к заявке
            if req_id is not None:
                assigned = [worker_ids[current_number % len(worker_ids)]]
                if current_number % 5 == 0 and len(worker_ids) > 1:
                    # иногда добавляем второго исполнителя
                    assigned.append(worker_ids[(current_number + 1) % len(worker_ids)])

                for wid in assigned:
                    bind.execute(
                        sa.text(
                            """
                            INSERT INTO request_workers (request_id, worker_id)
                            VALUES (:request_id, :worker_id)
                            """
                        ),
                        {'request_id': req_id, 'worker_id': wid},
                    )

            current_number += 1

        start_day += timedelta(days=1)


def downgrade():
    bind = op.get_bind()

    # Удаляем все DEMO-заявки и связи
    demo_requests = bind.execute(
        sa.text("SELECT id FROM requests WHERE description LIKE 'DEMO:%'")
    ).fetchall()
    demo_ids = [row[0] for row in demo_requests]

    if demo_ids:
        bind.execute(
            sa.text(
                "DELETE FROM request_workers WHERE request_id = ANY(:ids)"
            ),
            {'ids': demo_ids},
        )
        bind.execute(
            sa.text(
                "DELETE FROM requests WHERE id = ANY(:ids)"
            ),
            {'ids': demo_ids},
        )

    # Удаляем демо‑исполнителей
    bind.execute(
        sa.text(
            "DELETE FROM workers WHERE full_name LIKE 'Демо %'"
        )
    )

