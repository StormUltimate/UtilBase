"""Дополнительные API заявки: медиа, материалы, оплаты, чат, журнал."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import current_app, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from app.api.v1 import api_v1_bp
from app.api.v1.helpers import (
    api_error,
    can_see_request,
    get_client_operation_id_from_request,
    is_assigned_worker,
    is_duplicate_client_operation,
    is_executor_role,
    is_full_list_role,
    log_request_action,
    register_client_operation,
)
from app.extensions import db
from app.models.all_models import (
    ChatMessage,
    ChatParticipant,
    ChatThread,
    Media,
    Request,
    RequestDefect,
    RequestItem,
    RequestPayment,
    RequestStatus,
)


def _request_or_404(request_id: int):
    req = (
        Request.query.options(joinedload(Request.client), joinedload(Request.workers))
        .filter_by(id=request_id)
        .first()
    )
    if not req:
        return None, jsonify(api_error("not_found", "Заявка не найдена", 404)[0]), 404
    return req, None, None


def _check_access(request_id: int, *, write: bool = False):
    user = current_user
    if not user:
        return None, jsonify(api_error("unauthorized", "Пользователь не найден", 401)[0]), 401
    req, err_body, err_code = _request_or_404(request_id)
    if not req:
        return None, err_body, err_code
    if not can_see_request(user, req):
        return None, jsonify(api_error("forbidden", "Нет доступа к заявке", 403)[0]), 403
    if write and not (
        is_full_list_role(user) or is_assigned_worker(user, req) or is_executor_role(user)
    ):
        return (
            None,
            jsonify(api_error("forbidden", "Недостаточно прав на изменение заявки", 403)[0]),
            403,
        )
    return req, None, None


def _to_decimal(value: Any, field_name: str) -> Decimal:
    try:
        if value is None or value == "":
            return Decimal("0")
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Поле {field_name} должно быть числом")


def _item_to_dict(item: RequestItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "request_id": item.request_id,
        "item_type": item.item_type,
        "name": item.name,
        "quantity": float(item.quantity or 0),
        "unit_price": float(item.unit_price or 0),
        "line_total": float(item.line_total or 0),
        "source": item.source,
        "comment": item.comment,
        "created_by_user_id": item.created_by_user_id,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _payment_to_dict(p: RequestPayment) -> dict[str, Any]:
    return {
        "id": p.id,
        "request_id": p.request_id,
        "client_id": p.client_id,
        "amount": float(p.amount or 0),
        "payment_method": p.payment_method,
        "is_cash": bool(p.is_cash),
        "note": p.note,
        "received_by_user_id": p.received_by_user_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _message_to_dict(msg: ChatMessage) -> dict[str, Any]:
    return {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "author_user_id": msg.author_user_id,
        "message_text": msg.message_text,
        "is_edited": bool(msg.is_edited),
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "updated_at": msg.updated_at.isoformat() if msg.updated_at else None,
    }


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _media_to_dict(m: Media) -> dict[str, Any]:
    return {
        "id": m.id,
        "request_id": m.request_id,
        "file_path": m.file_path,
        "file_type": m.file_type,
        "content_type": m.content_type,
        "category": m.category,
        "file_size": m.file_size,
        "upload_date": m.upload_date.isoformat() if m.upload_date else None,
    }


def _defect_to_dict(d: RequestDefect) -> dict[str, Any]:
    return {
        "id": d.id,
        "request_id": d.request_id,
        "kind": d.kind,
        "description": d.description,
        "media_id": d.media_id,
        "created_by_user_id": d.created_by_user_id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@api_v1_bp.route("/requests/<int:request_id>/media", methods=["GET"])
@jwt_required()
def list_request_media(request_id: int):
    _, err_body, err_code = _check_access(request_id, write=False)
    if err_body:
        return err_body, err_code
    rows = (
        Media.query.filter_by(request_id=request_id)
        .order_by(Media.upload_date.desc().nullslast(), Media.id.desc())
        .all()
    )
    return jsonify({"items": [_media_to_dict(x) for x in rows]}), 200


@api_v1_bp.route("/requests/<int:request_id>/media", methods=["POST"])
@jwt_required()
def upload_request_media(request_id: int):
    client_operation_id = get_client_operation_id_from_request()
    if is_duplicate_client_operation(
        request_id, current_user.id if current_user else None, "media_upload", client_operation_id
    ):
        return jsonify({"ok": True, "duplicate": True}), 200
    req, err_body, err_code = _check_access(request_id, write=True)
    if err_body:
        return err_body, err_code

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(api_error("validation_error", "Передайте файл в поле file", 400)[0]), 400

    original = secure_filename(file.filename)
    suffix = Path(original).suffix.lower()
    generated = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex}{suffix}"
    relative = Path("requests") / str(request_id) / generated
    abs_dir = Path(current_app.config.get("MEDIA_DIR", "media")) / "requests" / str(request_id)
    abs_dir.mkdir(parents=True, exist_ok=True)
    abs_path = abs_dir / generated
    file.save(abs_path)

    content_type = (file.content_type or "").lower()
    if content_type.startswith("image/"):
        file_type = "photo"
    elif content_type.startswith("video/"):
        file_type = "video"
    else:
        file_type = "file"

    category = (request.form.get("category") or "").strip() or None
    if category and len(category) > 64:
        return jsonify(
            api_error("validation_error", "category не длиннее 64 символов", 400)[0]
        ), 400

    row = Media(
        request_id=request_id,
        client_id=req.client_id,
        file_path=str(relative).replace("\\", "/"),
        file_type=file_type,
        content_type=content_type or None,
        file_size=abs_path.stat().st_size if abs_path.exists() else None,
        created_by_user_id=current_user.id,
        upload_date=datetime.utcnow(),
        category=category,
    )
    db.session.add(row)
    log_request_action(
        request_id,
        current_user.id,
        "media_upload",
        extra={"media_id": None, "file_type": file_type, "path": row.file_path},
    )
    register_client_operation(
        request_id, current_user.id if current_user else None, "media_upload", client_operation_id
    )
    db.session.commit()
    return (
        jsonify(
            {
                "id": row.id,
                "request_id": row.request_id,
                "file_path": row.file_path,
                "file_type": row.file_type,
                "content_type": row.content_type,
                "file_size": row.file_size,
                "category": row.category,
            }
        ),
        201,
    )


@api_v1_bp.route("/requests/<int:request_id>/defects", methods=["GET"])
@jwt_required()
def list_request_defects(request_id: int):
    _, err_body, err_code = _check_access(request_id, write=False)
    if err_body:
        return err_body, err_code
    rows = (
        RequestDefect.query.filter_by(request_id=request_id)
        .order_by(RequestDefect.created_at.desc(), RequestDefect.id.desc())
        .all()
    )
    return jsonify({"items": [_defect_to_dict(x) for x in rows]}), 200


@api_v1_bp.route("/requests/<int:request_id>/defects", methods=["POST"])
@jwt_required()
def create_request_defect(request_id: int):
    client_operation_id = get_client_operation_id_from_request()
    if is_duplicate_client_operation(
        request_id, current_user.id if current_user else None, "defect_add", client_operation_id
    ):
        rows = (
            RequestDefect.query.filter_by(request_id=request_id)
            .order_by(RequestDefect.id.desc())
            .limit(1)
            .all()
        )
        if rows:
            return jsonify(_defect_to_dict(rows[0])), 200
        return jsonify({"ok": True, "duplicate": True}), 200
    req, err_body, err_code = _check_access(request_id, write=True)
    if err_body:
        return err_body, err_code
    if not (is_full_list_role(current_user) or is_assigned_worker(current_user, req)):
        return jsonify(api_error("forbidden", "Нужно быть назначенным на заявку", 403)[0]), 403
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").strip().lower()
    if kind not in ("equipment", "material"):
        return jsonify(api_error("validation_error", "kind: equipment или material", 400)[0]), 400
    description = (data.get("description") or "").strip()
    if not description:
        return jsonify(api_error("validation_error", "Укажите description", 400)[0]), 400
    media_id = data.get("media_id")
    if media_id is not None:
        try:
            media_id = int(media_id)
        except (TypeError, ValueError):
            return jsonify(
                api_error("validation_error", "media_id должен быть числом", 400)[0]
            ), 400
        m = Media.query.filter_by(id=media_id, request_id=request_id).first()
        if not m:
            return jsonify(
                api_error("validation_error", "Медиа не найдено для этой заявки", 400)[0]
            ), 400

    row = RequestDefect(
        request_id=request_id,
        kind=kind,
        description=description,
        media_id=media_id if media_id is not None else None,
        created_by_user_id=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.session.add(row)
    log_request_action(request_id, current_user.id, "defect_add", extra={"kind": kind})
    register_client_operation(
        request_id, current_user.id if current_user else None, "defect_add", client_operation_id
    )
    db.session.commit()
    return jsonify(_defect_to_dict(row)), 201


@api_v1_bp.route("/requests/<int:request_id>/items", methods=["GET"])
@jwt_required()
def list_request_items(request_id: int):
    _, err_body, err_code = _check_access(request_id, write=False)
    if err_body:
        return err_body, err_code

    rows = (
        RequestItem.query.filter_by(request_id=request_id)
        .order_by(RequestItem.created_at.asc(), RequestItem.id.asc())
        .all()
    )
    totals = {
        "works": 0.0,
        "materials": 0.0,
        "extra": 0.0,
        "total": 0.0,
    }
    for r in rows:
        line = float(r.line_total or 0)
        if r.item_type == "work":
            totals["works"] += line
        elif r.item_type == "extra":
            totals["extra"] += line
        else:
            totals["materials"] += line
    totals["total"] = totals["works"] + totals["materials"] + totals["extra"]
    return jsonify({"items": [_item_to_dict(r) for r in rows], "totals": totals}), 200


@api_v1_bp.route("/requests/<int:request_id>/items", methods=["POST"])
@jwt_required()
def create_request_item(request_id: int):
    client_operation_id = get_client_operation_id_from_request()
    if is_duplicate_client_operation(
        request_id, current_user.id if current_user else None, "item_add", client_operation_id
    ):
        rows = (
            RequestItem.query.filter_by(request_id=request_id)
            .order_by(RequestItem.id.desc())
            .limit(1)
            .all()
        )
        if rows:
            return jsonify(_item_to_dict(rows[0])), 200
        return jsonify({"ok": True, "duplicate": True}), 200
    _, err_body, err_code = _check_access(request_id, write=True)
    if err_body:
        return err_body, err_code
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(api_error("validation_error", "Поле name обязательно", 400)[0]), 400
    try:
        quantity = _to_decimal(data.get("quantity", 1), "quantity")
        unit_price = _to_decimal(data.get("unit_price", 0), "unit_price")
    except ValueError as exc:
        return jsonify(api_error("validation_error", str(exc), 400)[0]), 400

    line_total = quantity * unit_price
    row = RequestItem(
        request_id=request_id,
        item_type=(data.get("item_type") or "material").strip() or "material",
        name=name,
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
        source=(data.get("source") or None),
        comment=(data.get("comment") or None),
        created_by_user_id=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.session.add(row)
    log_request_action(request_id, current_user.id, "item_add", extra={"name": row.name})
    register_client_operation(
        request_id, current_user.id if current_user else None, "item_add", client_operation_id
    )
    db.session.commit()
    return jsonify(_item_to_dict(row)), 201


@api_v1_bp.route("/requests/<int:request_id>/items/<int:item_id>", methods=["PATCH"])
@jwt_required()
def patch_request_item(request_id: int, item_id: int):
    client_operation_id = get_client_operation_id_from_request()
    _, err_body, err_code = _check_access(request_id, write=True)
    if err_body:
        return err_body, err_code
    row = RequestItem.query.filter_by(id=item_id, request_id=request_id).first()
    if not row:
        return jsonify(api_error("not_found", "Позиция не найдена", 404)[0]), 404
    data = request.get_json(silent=True) or {}
    if "name" in data:
        row.name = (data.get("name") or "").strip() or row.name
    if "item_type" in data:
        row.item_type = (data.get("item_type") or row.item_type).strip() or row.item_type
    if "source" in data:
        row.source = data.get("source")
    if "comment" in data:
        row.comment = data.get("comment")
    if "quantity" in data:
        try:
            row.quantity = _to_decimal(data.get("quantity"), "quantity")
        except ValueError as exc:
            return jsonify(api_error("validation_error", str(exc), 400)[0]), 400
    if "unit_price" in data:
        try:
            row.unit_price = _to_decimal(data.get("unit_price"), "unit_price")
        except ValueError as exc:
            return jsonify(api_error("validation_error", str(exc), 400)[0]), 400
    row.line_total = Decimal(str(row.quantity or 0)) * Decimal(str(row.unit_price or 0))
    log_request_action(request_id, current_user.id, "item_update", extra={"item_id": row.id})
    register_client_operation(
        request_id, current_user.id if current_user else None, "item_update", client_operation_id
    )
    db.session.commit()
    return jsonify(_item_to_dict(row)), 200


@api_v1_bp.route("/requests/<int:request_id>/items/<int:item_id>", methods=["DELETE"])
@jwt_required()
def delete_request_item(request_id: int, item_id: int):
    client_operation_id = get_client_operation_id_from_request()
    if is_duplicate_client_operation(
        request_id, current_user.id if current_user else None, "item_delete", client_operation_id
    ):
        return jsonify({"ok": True, "duplicate": True}), 200
    _, err_body, err_code = _check_access(request_id, write=True)
    if err_body:
        return err_body, err_code
    row = RequestItem.query.filter_by(id=item_id, request_id=request_id).first()
    if not row:
        return jsonify(api_error("not_found", "Позиция не найдена", 404)[0]), 404
    db.session.delete(row)
    log_request_action(request_id, current_user.id, "item_delete", extra={"item_id": item_id})
    register_client_operation(
        request_id, current_user.id if current_user else None, "item_delete", client_operation_id
    )
    db.session.commit()
    return jsonify({"ok": True}), 200


@api_v1_bp.route("/requests/<int:request_id>/payments", methods=["GET"])
@jwt_required()
def list_request_payments(request_id: int):
    _, err_body, err_code = _check_access(request_id, write=False)
    if err_body:
        return err_body, err_code
    rows = (
        RequestPayment.query.filter_by(request_id=request_id)
        .order_by(RequestPayment.created_at.asc(), RequestPayment.id.asc())
        .all()
    )
    return jsonify({"items": [_payment_to_dict(p) for p in rows]}), 200


@api_v1_bp.route("/requests/<int:request_id>/payments", methods=["POST"])
@jwt_required()
def create_request_payment(request_id: int):
    client_operation_id = get_client_operation_id_from_request()
    if is_duplicate_client_operation(
        request_id, current_user.id if current_user else None, "payment_add", client_operation_id
    ):
        return jsonify({"ok": True, "duplicate": True}), 200
    req, err_body, err_code = _check_access(request_id, write=True)
    if err_body:
        return err_body, err_code
    data = request.get_json(silent=True) or {}
    try:
        amount = _to_decimal(data.get("amount"), "amount")
    except ValueError as exc:
        return jsonify(api_error("validation_error", str(exc), 400)[0]), 400

    row = RequestPayment(
        request_id=request_id,
        client_id=req.client_id,
        amount=amount,
        payment_method=(data.get("payment_method") or "cash"),
        is_cash=bool(data.get("is_cash", False)),
        note=data.get("note"),
        received_by_user_id=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.session.add(row)
    log_request_action(
        request_id,
        current_user.id,
        "payment_add",
        extra={"amount": float(amount), "is_cash": row.is_cash},
    )
    register_client_operation(
        request_id, current_user.id if current_user else None, "payment_add", client_operation_id
    )
    db.session.commit()
    total_paid = (
        db.session.query(db.func.coalesce(db.func.sum(RequestPayment.amount), 0))
        .filter(RequestPayment.request_id == request_id)
        .scalar()
    )
    request_total = float(req.total_price or 0)
    return (
        jsonify(
            {
                "payment": _payment_to_dict(row),
                "summary": {
                    "request_total": request_total,
                    "total_paid": float(total_paid or 0),
                    "delta": request_total - float(total_paid or 0),
                },
            }
        ),
        201,
    )


def _get_or_create_thread(request_id: int) -> ChatThread:
    thread = ChatThread.query.filter_by(request_id=request_id).first()
    if thread:
        return thread
    thread = ChatThread(
        request_id=request_id,
        created_by_user_id=current_user.id if current_user else None,
        is_archived=False,
        created_at=datetime.utcnow(),
    )
    db.session.add(thread)
    db.session.flush()
    return thread


@api_v1_bp.route("/requests/<int:request_id>/chat/messages", methods=["GET"])
@jwt_required()
def list_chat_messages(request_id: int):
    _, err_body, err_code = _check_access(request_id, write=False)
    if err_body:
        return err_body, err_code
    thread = ChatThread.query.filter_by(request_id=request_id).first()
    if not thread:
        return jsonify({"items": [], "thread_id": None}), 200
    rows = (
        ChatMessage.query.filter_by(thread_id=thread.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    return jsonify({"thread_id": thread.id, "items": [_message_to_dict(x) for x in rows]}), 200


@api_v1_bp.route("/requests/<int:request_id>/chat/messages", methods=["POST"])
@jwt_required()
def create_chat_message(request_id: int):
    client_operation_id = get_client_operation_id_from_request()
    if is_duplicate_client_operation(
        request_id, current_user.id if current_user else None, "chat_message", client_operation_id
    ):
        return jsonify({"ok": True, "duplicate": True}), 200
    _, err_body, err_code = _check_access(request_id, write=True)
    if err_body:
        return err_body, err_code
    data = request.get_json(silent=True) or {}
    message_text = (data.get("message_text") or "").strip()
    if not message_text:
        return jsonify(api_error("validation_error", "message_text обязателен", 400)[0]), 400

    thread = _get_or_create_thread(request_id)
    participant = ChatParticipant.query.filter_by(
        thread_id=thread.id, user_id=current_user.id
    ).first()
    if not participant:
        participant = ChatParticipant(
            thread_id=thread.id,
            user_id=current_user.id,
            created_at=datetime.utcnow(),
        )
        db.session.add(participant)
    participant.last_read_at = datetime.utcnow()

    msg = ChatMessage(
        thread_id=thread.id,
        author_user_id=current_user.id,
        message_text=message_text,
        is_edited=False,
        created_at=datetime.utcnow(),
    )
    db.session.add(msg)
    log_request_action(request_id, current_user.id, "chat_message", extra={"thread_id": thread.id})
    register_client_operation(
        request_id, current_user.id if current_user else None, "chat_message", client_operation_id
    )
    db.session.commit()
    return jsonify(_message_to_dict(msg)), 201


@api_v1_bp.route("/requests/<int:request_id>/logs", methods=["GET"])
@jwt_required()
def list_request_logs(request_id: int):
    _, err_body, err_code = _check_access(request_id, write=False)
    if err_body:
        return err_body, err_code
    rows = (
        Request.query.filter_by(id=request_id)
        .options(joinedload(Request.action_logs))
        .first()
        .action_logs
    )
    rows_sorted = sorted(rows, key=lambda x: (x.created_at or datetime.min, x.id or 0))
    return (
        jsonify(
            {
                "items": [
                    {
                        "id": r.id,
                        "action": r.action,
                        "user_id": r.user_id,
                        "old_status": r.old_status,
                        "new_status": r.new_status,
                        "old_mode": r.old_mode,
                        "new_mode": r.new_mode,
                        "extra": r.extra,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows_sorted
                ]
            }
        ),
        200,
    )


@api_v1_bp.route("/requests/summary", methods=["GET"])
@jwt_required()
def requests_summary():
    user = current_user
    if not user or not is_full_list_role(user):
        return jsonify(api_error("forbidden", "Сводка доступна диспетчеру/админу", 403)[0]), 403

    date_from = _parse_date((request.args.get("date_from") or "").strip())
    date_to = _parse_date((request.args.get("date_to") or "").strip())
    q = Request.query
    if date_from:
        q = q.filter(Request.planned_date >= date_from)
    if date_to:
        q = q.filter(Request.planned_date <= date_to)

    rows = q.all()
    by_status = {
        "pending": 0,
        "assigned": 0,
        "closed": 0,
        "overdue": 0,
        "cancelled": 0,
    }
    by_mode: dict[str, int] = {}
    by_service_type: dict[str, int] = {}
    by_visit_type: dict[str, int] = {}

    for r in rows:
        s = r.status.value if r.status else "assigned"
        by_status[s] = by_status.get(s, 0) + 1
        m = r.mode.value if r.mode else "normal"
        by_mode[m] = by_mode.get(m, 0) + 1
        st = r.service_type.value if r.service_type else "unknown"
        by_service_type[st] = by_service_type.get(st, 0) + 1
        vt = r.visit_type.value if r.visit_type else "repair"
        by_visit_type[vt] = by_visit_type.get(vt, 0) + 1

    total = len(rows)
    closed = by_status.get(RequestStatus.closed.value, 0)
    overdue = by_status.get(RequestStatus.overdue.value, 0)
    return (
        jsonify(
            {
                "period": {
                    "date_from": date_from.isoformat() if date_from else None,
                    "date_to": date_to.isoformat() if date_to else None,
                },
                "total": total,
                "closed_rate": (closed / total) if total else 0,
                "overdue_rate": (overdue / total) if total else 0,
                "by_status": by_status,
                "by_mode": by_mode,
                "by_service_type": by_service_type,
                "by_visit_type": by_visit_type,
            }
        ),
        200,
    )


@api_v1_bp.route("/requests/<int:request_id>/financial-summary", methods=["GET"])
@jwt_required()
def request_financial_summary(request_id: int):
    req, err_body, err_code = _check_access(request_id, write=False)
    if err_body:
        return err_body, err_code

    item_rows = RequestItem.query.filter_by(request_id=request_id).all()
    payment_rows = RequestPayment.query.filter_by(request_id=request_id).all()

    works = Decimal("0")
    materials = Decimal("0")
    extra = Decimal("0")
    for i in item_rows:
        line = Decimal(str(i.line_total or 0))
        if i.item_type == "work":
            works += line
        elif i.item_type == "extra":
            extra += line
        else:
            materials += line

    items_total = works + materials + extra
    paid_total = sum((Decimal(str(p.amount or 0)) for p in payment_rows), Decimal("0"))
    request_total = Decimal(str(req.total_price or 0))

    return (
        jsonify(
            {
                "request_id": request_id,
                "request_total": float(request_total),
                "items_total": float(items_total),
                "works_total": float(works),
                "materials_total": float(materials),
                "extra_total": float(extra),
                "paid_total": float(paid_total),
                "delta_to_request_total": float(request_total - paid_total),
                "delta_to_items_total": float(items_total - paid_total),
                "payments_count": len(payment_rows),
                "items_count": len(item_rows),
            }
        ),
        200,
    )
