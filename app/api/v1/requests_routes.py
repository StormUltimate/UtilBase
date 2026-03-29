"""Заявки: список, карточка, take / mode / close."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from flask import current_app, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import func, not_, or_
from sqlalchemy.orm import joinedload

from app.api.v1 import api_v1_bp
from app.api.v1.checklist_routes import get_checklist_completion_state
from app.api.v1.helpers import (
    allow_unassigned_pool,
    api_error,
    can_see_request,
    get_client_operation_id_from_request,
    is_assigned_worker,
    is_duplicate_client_operation,
    is_executor_role,
    is_full_list_role,
    log_request_action,
    register_client_operation,
    resolve_worker_id,
)
from app.extensions import db
from app.models.all_models import (
    Equipment,
    Media,
    Request,
    RequestMode,
    RequestStatus,
    ServiceType,
    VisitType,
    Worker,
)

# FSM режима выполнения (после назначения исполнителя)
_MODE_EDGES: dict[RequestMode, frozenset] = {
    RequestMode.normal: frozenset({RequestMode.on_way}),
    RequestMode.on_way: frozenset({RequestMode.arrived}),
    RequestMode.arrived: frozenset({RequestMode.in_progress}),
    RequestMode.in_progress: frozenset({RequestMode.waiting, RequestMode.completed}),
    RequestMode.waiting: frozenset({RequestMode.in_progress, RequestMode.completed}),
    RequestMode.completed: frozenset(),
}


def _interval_to_minutes(interval) -> int | None:
    if not interval:
        return None
    try:
        return max(0, int(interval.total_seconds() // 60))
    except Exception:
        return None


def _regulation_minutes(req: Request) -> int | None:
    """Норматив: часы из estimated_time (как во веб-форме) или максимум длительности из регламента оборудования."""
    if req.estimated_time is not None:
        return int(req.estimated_time) * 60
    eq = req.equipment
    if not eq:
        return None
    regs = getattr(eq, "regulations", None) or []
    best = 0
    for r in regs:
        m = _interval_to_minutes(getattr(r, "service_duration", None))
        if m:
            best = max(best, m)
    return best if best > 0 else None


def _actual_work_minutes(req: Request, *, now: datetime | None = None) -> int | None:
    """Факт «в работе»: от actual_start_time; окончание — actual_end_time или момент закрытия (ставится при close)."""
    if not req.actual_start_time:
        return None
    end = req.actual_end_time
    if end is None and req.status not in (RequestStatus.closed, RequestStatus.cancelled):
        end = now or datetime.utcnow()
    if end is None:
        return None
    delta = end - req.actual_start_time
    return max(0, int(delta.total_seconds() // 60))


def _request_loaded_for_response(request_id: int) -> Request | None:
    """Полная загрузка заявки для JSON (после commit/rollback, не под FOR UPDATE)."""
    return (
        Request.query.options(
            joinedload(Request.client),
            joinedload(Request.workers),
            joinedload(Request.equipment).selectinload(Equipment.regulations),
        )
        .filter_by(id=request_id)
        .first()
    )


def _jsonable(val: Any) -> Any:
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if hasattr(val, "value"):
        return val.value
    return val


def _request_to_dict(req: Request, *, detailed: bool = False) -> dict[str, Any]:
    client = req.client
    workers = [
        {"id": w.id, "full_name": w.full_name, "phone": w.phone} for w in (req.workers or [])
    ]
    reg_min = _regulation_minutes(req)
    act_min = _actual_work_minutes(req)
    out: dict[str, Any] = {
        "id": req.id,
        "request_number": req.request_number or str(req.id),
        "description": req.description,
        "status": req.status.value if req.status else None,
        "mode": req.mode.value if req.mode else None,
        "service_type": req.service_type.value if req.service_type else None,
        "visit_type": req.visit_type.value if req.visit_type else None,
        "type": req.type,
        "planned_date": req.planned_date.isoformat() if req.planned_date else None,
        "planned_start_time": req.planned_start_time.isoformat()
        if req.planned_start_time
        else None,
        "planned_end_time": req.planned_end_time.isoformat() if req.planned_end_time else None,
        "actual_start_time": req.actual_start_time.isoformat() if req.actual_start_time else None,
        "actual_end_time": req.actual_end_time.isoformat() if req.actual_end_time else None,
        "regulation_minutes": reg_min,
        "actual_work_minutes": act_min,
        "total_price": _jsonable(req.total_price) if req.total_price is not None else None,
        "workers": workers,
        "full_name": req.full_name or (client.full_name if client else None),
        "address": req.address or (client.address if client else None),
        "phone": req.phone or (client.phone if client else None),
    }
    if detailed:
        out["comment"] = req.comment
        out["client_id"] = req.client_id
        out["equipment_id"] = req.equipment_id
        out["contract_id"] = req.contract_id
        out["created_at"] = req.created_at.isoformat() if req.created_at else None
        out["updated_at"] = req.updated_at.isoformat() if req.updated_at else None
    return out


def _sync_overdue() -> None:
    """Пометить просроченные по плановой дате (как веб-раздел заявок)."""
    try:
        overdue = Request.query.filter(
            Request.planned_date < date.today(),
            Request.status.notin_(
                [RequestStatus.closed, RequestStatus.overdue, RequestStatus.cancelled]
            ),
        ).all()
        for r in overdue:
            r.status = RequestStatus.overdue
        if overdue:
            db.session.commit()
    except Exception:
        db.session.rollback()


def _base_query_for_user(user):
    q = Request.query.options(joinedload(Request.client), joinedload(Request.workers))
    if is_full_list_role(user):
        return q
    wid = resolve_worker_id(user)
    if wid is None:
        return None
    pool = allow_unassigned_pool()
    cond = Request.workers.any(Worker.id == wid)
    if pool:
        cond = or_(cond, not_(Request.workers.any()))
    return q.filter(cond)


@api_v1_bp.route("/requests", methods=["GET"])
@jwt_required()
def list_requests():
    user = current_user
    if not user:
        return jsonify(api_error("unauthorized", "Пользователь не найден", 401)[0]), 401

    if is_executor_role(user) and resolve_worker_id(user) is None:
        j, code = api_error(
            "no_worker_link",
            "Для учётной записи не задан исполнитель (worker_id или карточка Worker с id как у пользователя).",
            403,
        )
        return jsonify(j), code

    _sync_overdue()

    q = _base_query_for_user(user)
    if q is None:
        return jsonify({"items": [], "total": 0}), 200

    raw_filter = request.args.get("filter")
    if raw_filter is None and is_executor_role(user):
        filt = "active"
    else:
        filt = (raw_filter or "all").strip().lower()
    if filt == "today":
        q = q.filter(func.date(Request.planned_date) == date.today())
    elif filt == "overdue":
        q = q.filter(Request.status == RequestStatus.overdue)
    elif filt == "planned":
        q = q.filter(
            Request.planned_date > date.today(),
            Request.status.notin_([RequestStatus.closed, RequestStatus.cancelled]),
        )
    elif filt == "emergency":
        q = q.filter(Request.service_type == ServiceType.emergency)
    elif filt == "repair":
        q = q.filter(or_(Request.visit_type == VisitType.repair, Request.visit_type.is_(None)))
    elif filt == "active":
        q = q.filter(Request.status.notin_([RequestStatus.closed, RequestStatus.cancelled]))

    total = q.count()
    try:
        limit = min(int(request.args.get("limit", 200)), 500)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        limit, offset = 200, 0

    rows = (
        q.options(
            joinedload(Request.client),
            joinedload(Request.workers),
            joinedload(Request.equipment).selectinload(Equipment.regulations),
        )
        .order_by(Request.planned_date.desc().nullslast(), Request.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return (
        jsonify(
            {
                "items": [_request_to_dict(r, detailed=False) for r in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        ),
        200,
    )


@api_v1_bp.route("/requests/<int:request_id>", methods=["GET"])
@jwt_required()
def get_request(request_id: int):
    user = current_user
    if not user:
        return jsonify(api_error("unauthorized", "Пользователь не найден", 401)[0]), 401

    req = (
        Request.query.options(
            joinedload(Request.client),
            joinedload(Request.workers),
            joinedload(Request.equipment).selectinload(Equipment.regulations),
        )
        .filter_by(id=request_id)
        .first()
    )
    if not req:
        j, code = api_error("not_found", "Заявка не найдена", 404)
        return jsonify(j), code
    if not can_see_request(user, req):
        j, code = api_error("forbidden", "Нет доступа к заявке", 403)
        return jsonify(j), code
    return jsonify(_request_to_dict(req, detailed=True)), 200


@api_v1_bp.route("/requests/<int:request_id>/take", methods=["POST"])
@jwt_required()
def take_request(request_id: int):
    client_operation_id = get_client_operation_id_from_request()
    user = current_user
    if not user:
        return jsonify(api_error("unauthorized", "Пользователь не найден", 401)[0]), 401
    if not is_executor_role(user):
        j, code = api_error("forbidden", "Действие доступно исполнителю (мастер/инженер)", 403)
        return jsonify(j), code

    wid = resolve_worker_id(user)
    if wid is None:
        j, code = api_error("no_worker_link", "Не задан исполнитель для пользователя", 403)
        return jsonify(j), code

    worker = Worker.query.get(wid)
    if not worker or not worker.is_active:
        j, code = api_error("invalid_worker", "Исполнитель не найден или неактивен", 403)
        return jsonify(j), code

    # Нельзя совмещать joinedload с FOR UPDATE в PostgreSQL (JOIN + блокировка → 500).
    req = Request.query.filter_by(id=request_id).with_for_update().first()
    if not req:
        j, code = api_error("not_found", "Заявка не найдена", 404)
        return jsonify(j), code

    if not can_see_request(user, req):
        db.session.rollback()
        j, code = api_error("forbidden", "Нет доступа к заявке", 403)
        return jsonify(j), code

    if req.status in (RequestStatus.closed, RequestStatus.cancelled):
        db.session.rollback()
        j, code = api_error("invalid_state", "Заявка закрыта или отменена", 409)
        return jsonify(j), code

    if req.workers and any(w.id == wid for w in req.workers):
        db.session.rollback()
        fresh = _request_loaded_for_response(request_id)
        if not fresh:
            j, code = api_error("not_found", "Заявка не найдена", 404)
            return jsonify(j), code
        return jsonify(_request_to_dict(fresh, detailed=True)), 200

    if req.workers and not any(w.id == wid for w in req.workers):
        db.session.rollback()
        j, code = api_error("already_assigned", "Заявка уже назначена другим исполнителям", 409)
        return jsonify(j), code

    if not req.workers:
        req.workers.append(worker)
        old_s = req.status.value if req.status else None
        req.updated_by_user_id = user.id
        req.updated_at = datetime.utcnow()
        log_request_action(
            req.id,
            user.id,
            "take",
            old_status=old_s,
            new_status=req.status.value if req.status else None,
        )
        register_client_operation(req.id, user.id, "take", client_operation_id)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            j, code = api_error("server_error", "Не удалось сохранить", 500)
            return jsonify(j), code

        fresh = _request_loaded_for_response(request_id)
        if not fresh:
            j, code = api_error("not_found", "Заявка не найдена", 404)
            return jsonify(j), code
        return jsonify(_request_to_dict(fresh, detailed=True)), 200

    db.session.rollback()
    j, code = api_error("server_error", "Неконсистентное состояние заявки", 500)
    return jsonify(j), code


@api_v1_bp.route("/requests/<int:request_id>/mode", methods=["POST"])
@jwt_required()
def set_request_mode(request_id: int):
    client_operation_id = get_client_operation_id_from_request()
    user = current_user
    if not user:
        return jsonify(api_error("unauthorized", "Пользователь не найден", 401)[0]), 401
    if not is_executor_role(user):
        j, code = api_error("forbidden", "Действие доступно исполнителю", 403)
        return jsonify(j), code

    wid = resolve_worker_id(user)
    if wid is None:
        j, code = api_error("no_worker_link", "Не задан исполнитель для пользователя", 403)
        return jsonify(j), code

    worker = Worker.query.get(wid)
    if not worker or not worker.is_active:
        j, code = api_error("invalid_worker", "Исполнитель не найден или неактивен", 403)
        return jsonify(j), code

    data = request.get_json(silent=True) or {}
    raw_mode = (data.get("mode") or "").strip()
    if not raw_mode:
        j, code = api_error("validation_error", "Укажите mode (например on_way)", 400)
        return jsonify(j), code

    try:
        new_mode = RequestMode(raw_mode)
    except ValueError:
        j, code = api_error("validation_error", f"Неизвестный режим: {raw_mode}", 400)
        return jsonify(j), code

    req = Request.query.options(joinedload(Request.workers)).get(request_id)
    if not req:
        j, code = api_error("not_found", "Заявка не найдена", 404)
        return jsonify(j), code

    if not can_see_request(user, req):
        j, code = api_error("forbidden", "Нет доступа к заявке", 403)
        return jsonify(j), code

    if is_duplicate_client_operation(req.id, user.id, "mode", client_operation_id):
        return jsonify(_request_to_dict(req, detailed=True)), 200

    if req.status in (RequestStatus.closed, RequestStatus.cancelled):
        j, code = api_error("invalid_state", "Заявка закрыта или отменена", 409)
        return jsonify(j), code

    # «В пути» без исполнителя — назначить текущего (ТЗ)
    if new_mode == RequestMode.on_way and not req.workers:
        req.workers.append(worker)

    if not is_assigned_worker(user, req):
        j, code = api_error("forbidden", "Сначала возьмите заявку или будьте назначены", 403)
        return jsonify(j), code

    old_mode = req.mode
    allowed = _MODE_EDGES.get(old_mode, frozenset())
    if new_mode not in allowed:
        j, code = api_error(
            "conflict_fsm",
            f"Переход {old_mode.value} → {new_mode.value} недопустим",
            409,
        )
        return jsonify(j), code

    req.mode = new_mode
    req.updated_by_user_id = user.id
    req.updated_at = datetime.utcnow()
    if new_mode == RequestMode.in_progress and not req.actual_start_time:
        req.actual_start_time = datetime.utcnow()
    # Фактическое окончание работ — только при закрытии заявки (close), не при mode=completed

    log_request_action(
        req.id,
        user.id,
        "mode_change",
        old_mode=old_mode.value if old_mode else None,
        new_mode=new_mode.value,
    )
    register_client_operation(req.id, user.id, "mode", client_operation_id)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        j, code = api_error("server_error", "Не удалось сохранить", 500)
        return jsonify(j), code

    return jsonify(_request_to_dict(req, detailed=True)), 200


@api_v1_bp.route("/requests/<int:request_id>/close", methods=["POST"])
@jwt_required()
def close_request(request_id: int):
    client_operation_id = get_client_operation_id_from_request()
    user = current_user
    if not user:
        return jsonify(api_error("unauthorized", "Пользователь не найден", 401)[0]), 401
    if not is_executor_role(user):
        j, code = api_error("forbidden", "Закрытие доступно исполнителю", 403)
        return jsonify(j), code

    wid = resolve_worker_id(user)
    if wid is None:
        j, code = api_error("no_worker_link", "Не задан исполнитель для пользователя", 403)
        return jsonify(j), code

    req = Request.query.options(joinedload(Request.workers)).get(request_id)
    if not req:
        j, code = api_error("not_found", "Заявка не найдена", 404)
        return jsonify(j), code

    if not can_see_request(user, req):
        j, code = api_error("forbidden", "Нет доступа к заявке", 403)
        return jsonify(j), code

    if not is_assigned_worker(user, req):
        j, code = api_error("forbidden", "Вы не назначены на эту заявку", 403)
        return jsonify(j), code

    if is_duplicate_client_operation(req.id, user.id, "close", client_operation_id):
        return jsonify(_request_to_dict(req, detailed=True)), 200

    if req.status in (RequestStatus.closed, RequestStatus.cancelled):
        j, code = api_error("invalid_state", "Заявка уже закрыта или отменена", 409)
        return jsonify(j), code

    if current_app.config.get("API_CLOSE_REQUIRES_COMPLETED_MODE", True):
        if req.mode != RequestMode.completed:
            j, code = api_error(
                "conflict_fsm",
                "Закрытие только после режима completed",
                409,
            )
            return jsonify(j), code
    if current_app.config.get("API_CLOSE_REQUIRES_CHECKLIST", True):
        checklist_state = get_checklist_completion_state(req)
        if not checklist_state.get("can_close_by_checklist", True):
            j, code = api_error(
                "conflict_fsm",
                "Заполните обязательные пункты чек-листа перед закрытием",
                409,
            )
            return jsonify({**j, "details": checklist_state}), code
    min_photos = int(current_app.config.get("API_CLOSE_MIN_PHOTOS", 1))
    if min_photos > 0:
        photos_count = Media.query.filter(
            Media.request_id == req.id,
            or_(
                Media.file_type == "photo",
                Media.content_type.ilike("image/%"),
            ),
        ).count()
        if photos_count < min_photos:
            j, code = api_error(
                "conflict_fsm",
                f"Перед закрытием добавьте минимум {min_photos} фото",
                409,
            )
            return jsonify(j), code

    old_s = req.status.value if req.status else None
    old_m = req.mode.value if req.mode else None
    req.status = RequestStatus.closed
    req.actual_end_time = datetime.utcnow()
    req.updated_by_user_id = user.id
    req.updated_at = datetime.utcnow()

    log_request_action(
        req.id,
        user.id,
        "close",
        old_status=old_s,
        new_status=RequestStatus.closed.value,
        old_mode=old_m,
        new_mode=old_m,
    )
    register_client_operation(req.id, user.id, "close", client_operation_id)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        j, code = api_error("server_error", "Не удалось сохранить", 500)
        return jsonify(j), code

    req = Request.query.options(joinedload(Request.client), joinedload(Request.workers)).get(
        request_id
    )
    return jsonify(_request_to_dict(req, detailed=True)), 200
