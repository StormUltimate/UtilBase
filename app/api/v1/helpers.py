"""Права и вспомогательные функции для /api/v1."""

from __future__ import annotations

from typing import Any

from flask import current_app, request

from app.extensions import db
from app.models.all_models import Request, RequestActionLog, RequestClientOperation, Users, Worker

# Роли с полным доступом к списку заявок (как диспетчер)
ROLE_FULL_LIST = frozenset({"admin", "dispatcher"})
# Исполнители в поле
ROLE_EXECUTOR = frozenset({"master", "engineer"})


def api_error(code: str, message: str, http_status: int) -> tuple[dict[str, Any], int]:
    return {"error": {"code": code, "message": message}}, http_status


def resolve_worker_id(user: Users) -> int | None:
    """Связка пользователя с карточкой исполнителя: users.worker_id или legacy Worker.id == User.id."""
    if getattr(user, "worker_id", None):
        w = Worker.query.get(user.worker_id)
        if w and w.is_active:
            return w.id
    legacy = Worker.query.get(user.id)
    if legacy and legacy.is_active:
        return legacy.id
    return None


def is_full_list_role(user: Users) -> bool:
    return user.role in ROLE_FULL_LIST


def is_executor_role(user: Users) -> bool:
    return user.role in ROLE_EXECUTOR


def allow_unassigned_pool() -> bool:
    return bool(current_app.config.get("API_ALLOW_UNASSIGNED_POOL", True))


def can_see_request(user: Users, req: Request) -> bool:
    if is_full_list_role(user):
        return True
    wid = resolve_worker_id(user)
    if wid is None:
        return False
    if not req.workers:
        return allow_unassigned_pool()
    return any(w.id == wid for w in req.workers)


def is_assigned_worker(user: Users, req: Request) -> bool:
    wid = resolve_worker_id(user)
    if wid is None:
        return False
    return any(w.id == wid for w in req.workers)


def log_request_action(
    request_id: int,
    user_id: int | None,
    action: str,
    *,
    old_status: str | None = None,
    new_status: str | None = None,
    old_mode: str | None = None,
    new_mode: str | None = None,
    extra: Any = None,
) -> None:
    row = RequestActionLog(
        request_id=request_id,
        user_id=user_id,
        action=action,
        old_status=old_status,
        new_status=new_status,
        old_mode=old_mode,
        new_mode=new_mode,
        extra=extra,
    )
    db.session.add(row)


def get_client_operation_id_from_request() -> str | None:
    """
    Поддержка offline outbox:
    - JSON: client_operation_id
    - multipart/form-data: client_operation_id
    - Header: X-Client-Operation-Id
    """
    cid = None
    try:
        data = request.get_json(silent=True) or {}
        cid = (data.get("client_operation_id") or "").strip()
    except Exception:
        cid = None
    if not cid:
        cid = (request.form.get("client_operation_id") or "").strip()
    if not cid:
        cid = (request.headers.get("X-Client-Operation-Id") or "").strip()
    return cid or None


def is_duplicate_client_operation(
    request_id: int,
    user_id: int | None,
    operation_type: str,
    client_operation_id: str | None,
) -> bool:
    if not client_operation_id:
        return False
    row = RequestClientOperation.query.filter_by(
        request_id=request_id,
        user_id=user_id,
        operation_type=operation_type,
        client_operation_id=client_operation_id,
    ).first()
    return row is not None


def register_client_operation(
    request_id: int,
    user_id: int | None,
    operation_type: str,
    client_operation_id: str | None,
) -> None:
    if not client_operation_id:
        return
    row = RequestClientOperation(
        request_id=request_id,
        user_id=user_id,
        operation_type=operation_type,
        client_operation_id=client_operation_id,
    )
    db.session.add(row)
