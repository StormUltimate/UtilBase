"""Загрузка данных план-графика: заявки, смены, исполнители (оптимизированные запросы)."""

from __future__ import annotations

import calendar as cal_module
import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.all_models import (
    Client,
    Contract,
    Equipment,
    Request,
    RequestStatus,
    Users,
    Worker,
    WorkerShift,
    request_workers,
)
from app.utils.contract_wizard import has_forbidden_gas
from app.utils.request_calendar import planned_range_for_request, worker_display_color

EXECUTOR_ROLES = ("master", "engineer")


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def period_bounds(anchor: date, view: str) -> tuple[date, date]:
    view = (view or "week").lower()
    if view == "day":
        return anchor, anchor
    if view == "week":
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
        return start, end
    if view == "month":
        first = anchor.replace(day=1)
        last_day = cal_module.monthrange(anchor.year, anchor.month)[1]
        last = date(anchor.year, anchor.month, last_day)
        return first, last
    return anchor, anchor


def active_executor_workers():
    return (
        Worker.query.join(Users, Users.worker_id == Worker.id)
        .filter(Worker.is_active.is_(True), Users.role.in_(EXECUTOR_ROLES))
        .order_by(Worker.full_name)
    )


def is_maintenance_engineering_contract(c: Contract | None) -> bool:
    if not c:
        return False
    if c.maintenance_wizard_json and str(c.maintenance_wizard_json).strip():
        return True
    ct = (c.contract_type or "").lower()
    return "обслуж" in ct or "инженерн" in ct


def _request_from_contract_scope(req: Request) -> bool:
    return bool(req.contract_scope_uid)


def _wizard_dict(contract: Contract | None) -> dict[str, Any]:
    if not contract or not contract.maintenance_wizard_json:
        return {}
    try:
        return json.loads(contract.maintenance_wizard_json)
    except (json.JSONDecodeError, TypeError):
        return {}


def collect_gas_warnings(requests: list[Request]) -> list[str]:
    msgs: list[str] = []
    seen: set[int] = set()
    for req in requests:
        c = req.contract
        if not c or not c.maintenance_wizard_json:
            continue
        if c.id in seen:
            continue
        w = _wizard_dict(c)
        if has_forbidden_gas(w):
            seen.add(c.id)
            msgs.append(
                f"Договор #{c.id}: в мастере указано топливо «природный газ» — "
                "обслуживание такого оборудования не выполняется (региональная служба)."
            )
    return msgs


def _base_request_query():
    return Request.query.options(
        joinedload(Request.client),
        joinedload(Request.equipment),
        joinedload(Request.contract),
        joinedload(Request.workers),
    )


def fetch_requests_for_period(
    start_d: date,
    end_d: date,
    *,
    q_search: str | None = None,
    worker_ids: list[int] | None = None,
    statuses: list[str] | None = None,
    equipment_types: list[str] | None = None,
    maintenance_only: bool = False,
) -> list[Request]:
    rq = _base_request_query().filter(
        Request.planned_date.isnot(None),
        Request.planned_date >= start_d,
        Request.planned_date <= end_d,
    )
    if statuses:
        by_val = {e.value: e for e in RequestStatus}
        st_enum = [by_val[s] for s in statuses if s in by_val]
        if st_enum:
            rq = rq.filter(Request.status.in_(st_enum))
    else:
        rq = rq.filter(Request.status != RequestStatus.cancelled)

    if q_search:
        term = f"%{q_search.strip()}%"
        rq = rq.outerjoin(Client, Request.client_id == Client.id).filter(
            or_(
                Request.description.ilike(term),
                Request.full_name.ilike(term),
                Request.address.ilike(term),
                Client.full_name.ilike(term),
                Client.address.ilike(term),
            )
        )

    if equipment_types:
        rq = rq.join(Equipment, Request.equipment_id == Equipment.id).filter(
            Equipment.type.in_(equipment_types)
        )

    if maintenance_only:
        rq = rq.join(Contract, Request.contract_id == Contract.id, isouter=False).filter(
            or_(
                Contract.maintenance_wizard_json.isnot(None),
                Contract.contract_type.ilike("%обслуж%"),
            )
        )

    if worker_ids:
        rq = rq.join(request_workers, Request.id == request_workers.c.request_id).filter(
            request_workers.c.worker_id.in_(worker_ids)
        )

    rows = rq.all()
    seen: set[int] = set()
    out: list[Request] = []
    for r in rows:
        if r.id not in seen:
            seen.add(r.id)
            out.append(r)
    return out


def fetch_shifts_for_period(
    start_d: date, end_d: date, worker_ids: list[int] | None = None
) -> list[WorkerShift]:
    q = (
        WorkerShift.query.options(joinedload(WorkerShift.worker))
        .join(Worker)
        .join(Users, Users.worker_id == Worker.id)
        .filter(
            WorkerShift.shift_date >= start_d,
            WorkerShift.shift_date <= end_d,
            Worker.is_active.is_(True),
            Users.role.in_(EXECUTOR_ROLES),
        )
    )
    if worker_ids:
        q = q.filter(WorkerShift.worker_id.in_(worker_ids))
    return q.all()


def fetch_unassigned_for_day(day: date, statuses: list[str] | None = None) -> list[Request]:
    rq = _base_request_query().filter(
        Request.planned_date == day,
        ~Request.workers.any(),
        Request.status != RequestStatus.cancelled,
    )
    if statuses:
        by_val = {e.value: e for e in RequestStatus}
        st_enum = [by_val[s] for s in statuses if s in by_val]
        if st_enum:
            rq = rq.filter(Request.status.in_(st_enum))
    return rq.all()


def serialize_worker(w: Worker, stats: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": w.id,
        "name": w.full_name,
        "color": worker_display_color(w),
        "stats": stats or {},
    }


def _serialize_request_block(
    req: Request,
    worker_id: int,
    wcolor: str,
) -> dict[str, Any] | None:
    start, end = planned_range_for_request(req)
    if not start or not end:
        return None
    client_name = req.client.full_name if req.client else (req.full_name or "—")
    addr = (req.client.address if req.client else None) or (req.address or "")
    eq_label = ""
    if req.equipment:
        eq_label = " · ".join(
            x for x in (req.equipment.type, req.equipment.brand, req.equipment.model) if x
        )
    title = client_name
    if eq_label:
        title = f"{client_name} — {eq_label}"
    c = req.contract
    return {
        "id": f"r{req.id}-w{worker_id}",
        "request_id": req.id,
        "worker_id": worker_id,
        "color": wcolor,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "title": title[:180],
        "client_label": client_name,
        "object_label": addr[:120] if addr else "",
        "equipment_label": eq_label[:120] if eq_label else "",
        "from_contract": _request_from_contract_scope(req),
        "maintenance_contract": is_maintenance_engineering_contract(c),
        "status": req.status.value if req.status else None,
        "type": req.type or "",
        "visit_type": req.visit_type.value if req.visit_type else None,
        "description": (req.description or "")[:500],
        "request_number": req.request_number or str(req.id),
    }


def build_timeline_payload(
    *,
    start_d: date,
    end_d: date,
    view: str,
    day_for_unassigned: date,
    filters: dict[str, Any],
    workers_override: list[Worker] | None = None,
) -> dict[str, Any]:
    """Единый JSON для schedule.js: исполнители, смены, блоки заявок (по строке на мастера)."""
    worker_ids = filters.get("worker_ids") or None
    statuses = filters.get("statuses") or None
    eq_types = filters.get("equipment_types") or None
    maintenance_only = bool(filters.get("maintenance_only"))
    q_search = filters.get("q") or None

    workers_list = (
        workers_override if workers_override is not None else active_executor_workers().all()
    )
    if worker_ids:
        workers_list = [w for w in workers_list if w.id in worker_ids]

    requests = fetch_requests_for_period(
        start_d,
        end_d,
        q_search=q_search,
        worker_ids=worker_ids,
        statuses=statuses,
        equipment_types=eq_types,
        maintenance_only=maintenance_only,
    )

    shifts_db = fetch_shifts_for_period(
        start_d, end_d, [w.id for w in workers_list] if workers_list else None
    )

    shifts_out: list[dict[str, Any]] = []
    for s in shifts_db:
        if s.worker_id not in {w.id for w in workers_list}:
            continue
        t0 = datetime.combine(s.shift_date, s.time_start)
        t1 = datetime.combine(s.shift_date, s.time_end)
        if t1 <= t0:
            t1 = t0 + timedelta(hours=1)
        wc = worker_display_color(s.worker)
        shifts_out.append(
            {
                "id": f"shift-{s.id}",
                "worker_id": s.worker_id,
                "start": t0.isoformat(),
                "end": t1.isoformat(),
                "color": wc,
            }
        )

    blocks: list[dict[str, Any]] = []
    for req in requests:
        assigned = list(req.workers)
        if not assigned:
            continue
        for w in assigned:
            if workers_list and w.id not in {x.id for x in workers_list}:
                continue
            col = worker_display_color(w)
            blk = _serialize_request_block(req, w.id, col)
            if blk:
                blocks.append(blk)

    unassigned = fetch_unassigned_for_day(day_for_unassigned, statuses=statuses)
    unassigned_out = []
    for req in unassigned:
        start, end = planned_range_for_request(req)
        if not start:
            continue
        unassigned_out.append(
            {
                "request_id": req.id,
                "title": (req.description or f"Заявка #{req.id}")[:160],
                "client_label": (req.client.full_name if req.client else req.full_name) or "—",
                "start": start.isoformat(),
                "end": end.isoformat() if end else None,
                "status": req.status.value if req.status else None,
            }
        )

    gas_messages = collect_gas_warnings(requests)

    # Статистика загрузки: доля времени заявок относительно смены по каждому мастеру за период
    load_pct: dict[str, float] = {}
    shift_ms_by_worker: dict[int, float] = {}
    req_ms_by_worker: dict[int, float] = {}
    for s in shifts_db:
        if s.worker_id not in shift_ms_by_worker:
            shift_ms_by_worker[s.worker_id] = 0.0
        t0 = datetime.combine(s.shift_date, s.time_start)
        t1 = datetime.combine(s.shift_date, s.time_end)
        if t1 <= t0:
            t1 = t0 + timedelta(hours=8)
        shift_ms_by_worker[s.worker_id] += (t1 - t0).total_seconds() * 1000
    for b in blocks:
        wid = b["worker_id"]
        try:
            a = datetime.fromisoformat(b["start"])
            e = datetime.fromisoformat(b["end"])
        except Exception:
            continue
        req_ms_by_worker[wid] = req_ms_by_worker.get(wid, 0.0) + max(
            0, (e - a).total_seconds() * 1000
        )
    for wid, sms in shift_ms_by_worker.items():
        rms = req_ms_by_worker.get(wid, 0.0)
        load_pct[str(wid)] = round(min(100.0, (rms / sms) * 100.0), 1) if sms > 0 else 0.0

    return {
        "period": {
            "start": start_d.isoformat(),
            "end": end_d.isoformat(),
            "view": view,
        },
        "workers": [
            serialize_worker(w, {"load_percent": load_pct.get(str(w.id), 0.0)})
            for w in workers_list
        ],
        "shifts": shifts_out,
        "blocks": blocks,
        "unassigned": unassigned_out,
        "warnings": {"gas": bool(gas_messages), "messages": gas_messages},
    }


def distinct_equipment_types() -> list[str]:
    rows = (
        db.session.query(Equipment.type)
        .filter(Equipment.type.isnot(None), Equipment.type != "")
        .distinct()
        .order_by(Equipment.type)
        .limit(300)
        .all()
    )
    return [r[0] for r in rows if r[0]]
