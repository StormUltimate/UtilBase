"""Чек-листы по заявке: шаблон и отправка ответов."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy.orm import joinedload

from app.api.v1 import api_v1_bp
from app.api.v1.helpers import can_see_request, is_assigned_worker, is_executor_role
from app.extensions import db
from app.models.all_models import (
    ChecklistTemplate,
    Request,
    RequestChecklistAnswer,
)


def _api_error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _resolve_template_for_request(req: Request) -> ChecklistTemplate | None:
    if req.checklist_template_id:
        pinned = (
            ChecklistTemplate.query.options(joinedload(ChecklistTemplate.items))
            .filter(
                ChecklistTemplate.id == req.checklist_template_id,
                ChecklistTemplate.is_active.is_(True),
            )
            .first()
        )
        if pinned:
            return pinned

    if req.equipment_id:
        by_equipment = (
            ChecklistTemplate.query.options(joinedload(ChecklistTemplate.items))
            .filter(
                ChecklistTemplate.is_active.is_(True),
                ChecklistTemplate.equipment_id == req.equipment_id,
            )
            .order_by(ChecklistTemplate.id.desc())
            .first()
        )
        if by_equipment:
            return by_equipment

    fallback = (
        ChecklistTemplate.query.options(joinedload(ChecklistTemplate.items))
        .filter(
            ChecklistTemplate.is_active.is_(True),
            ChecklistTemplate.is_default.is_(True),
        )
        .order_by(ChecklistTemplate.id.desc())
        .first()
    )
    if fallback:
        return fallback

    # если default не найден — любой активный (защита от пустой БД)
    return (
        ChecklistTemplate.query.options(joinedload(ChecklistTemplate.items))
        .filter(ChecklistTemplate.is_active.is_(True))
        .order_by(ChecklistTemplate.id.asc())
        .first()
    )


def get_checklist_completion_state(req: Request) -> dict[str, Any]:
    """Состояние заполнения чек-листа для правил закрытия."""
    template = _resolve_template_for_request(req)
    if not template:
        return {
            "has_template": False,
            "required_total": 0,
            "required_done": 0,
            "can_close_by_checklist": True,
            "missing_item_ids": [],
        }

    item_ids = [x.id for x in template.items]
    if not item_ids:
        return {
            "has_template": True,
            "template_id": template.id,
            "required_total": 0,
            "required_done": 0,
            "can_close_by_checklist": True,
            "missing_item_ids": [],
        }

    answers = RequestChecklistAnswer.query.filter(
        RequestChecklistAnswer.request_id == req.id,
        RequestChecklistAnswer.template_item_id.in_(item_ids),
    ).all()
    by_item = {a.template_item_id: a for a in answers}

    required_total = 0
    required_done = 0
    missing: list[int] = []
    for item in template.items:
        if not item.is_required:
            continue
        required_total += 1
        ans = by_item.get(item.id)
        is_done = False
        if ans:
            if item.item_type == "boolean":
                is_done = bool(ans.checked)
            elif item.item_type == "number":
                is_done = ans.value_number is not None
            else:
                is_done = bool((ans.value_text or "").strip())
        if is_done:
            required_done += 1
        else:
            missing.append(item.id)

    return {
        "has_template": True,
        "template_id": template.id,
        "required_total": required_total,
        "required_done": required_done,
        "can_close_by_checklist": required_done >= required_total,
        "missing_item_ids": missing,
    }


@api_v1_bp.route("/requests/<int:request_id>/checklist-template", methods=["GET"])
@jwt_required()
def get_checklist_template(request_id: int):
    req = (
        Request.query.options(joinedload(Request.equipment), joinedload(Request.workers))
        .filter_by(id=request_id)
        .first()
    )
    if not req:
        return _api_error("not_found", "Заявка не найдена", 404)
    if not current_user or not can_see_request(current_user, req):
        return _api_error("forbidden", "Нет доступа к заявке", 403)

    template = _resolve_template_for_request(req)
    if not template:
        return jsonify({"template": None, "items": []}), 200

    item_ids = [x.id for x in template.items]
    answers = []
    if item_ids:
        answers = RequestChecklistAnswer.query.filter(
            RequestChecklistAnswer.request_id == req.id,
            RequestChecklistAnswer.template_item_id.in_(item_ids),
        ).all()
    ans_by_item = {a.template_item_id: a for a in answers}

    items = []
    for item in sorted(template.items, key=lambda x: (x.item_order or 0, x.id)):
        ans = ans_by_item.get(item.id)
        items.append(
            {
                "id": item.id,
                "title": item.title,
                "order": item.item_order,
                "is_required": bool(item.is_required),
                "item_type": item.item_type,
                "answer": {
                    "checked": ans.checked if ans else None,
                    "value_text": ans.value_text if ans else None,
                    "value_number": float(ans.value_number)
                    if ans and ans.value_number is not None
                    else None,
                    "media_id": ans.media_id if ans else None,
                    "answered_at": ans.answered_at.isoformat() if ans and ans.answered_at else None,
                },
            }
        )

    state = get_checklist_completion_state(req)
    return (
        jsonify(
            {
                "template": {
                    "id": template.id,
                    "name": template.name,
                    "equipment_type": template.equipment_type,
                    "is_default": bool(template.is_default),
                },
                "items": items,
                "state": state,
            }
        ),
        200,
    )


@api_v1_bp.route("/requests/<int:request_id>/checklist-submit", methods=["POST"])
@jwt_required()
def submit_checklist(request_id: int):
    req = (
        Request.query.options(joinedload(Request.equipment), joinedload(Request.workers))
        .filter_by(id=request_id)
        .first()
    )
    if not req:
        return _api_error("not_found", "Заявка не найдена", 404)
    if not current_user or not can_see_request(current_user, req):
        return _api_error("forbidden", "Нет доступа к заявке", 403)
    if not is_executor_role(current_user):
        return _api_error("forbidden", "Чек-лист может заполнять исполнитель", 403)
    if not is_assigned_worker(current_user, req):
        return _api_error("forbidden", "Заявка должна быть назначена вам", 403)

    template = _resolve_template_for_request(req)
    if not template:
        return _api_error("validation_error", "Для заявки нет шаблона чек-листа", 409)

    data = request.get_json(silent=True) or {}
    entries = data.get("items") or []
    if not isinstance(entries, list):
        return _api_error("validation_error", "Поле items должно быть массивом", 400)

    template_items = {i.id: i for i in template.items}
    if not template_items:
        return jsonify(
            {"ok": True, "updated": 0, "state": get_checklist_completion_state(req)}
        ), 200

    updated = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("item_id")
        if not item_id or item_id not in template_items:
            continue
        item = template_items[item_id]
        ans = RequestChecklistAnswer.query.filter_by(
            request_id=req.id,
            template_item_id=item_id,
        ).first()
        if not ans:
            ans = RequestChecklistAnswer(
                request_id=req.id,
                template_item_id=item_id,
                answered_by_user_id=current_user.id,
                answered_at=datetime.utcnow(),
            )
            db.session.add(ans)

        if item.item_type == "boolean":
            ans.checked = bool(entry.get("checked", False))
        elif item.item_type == "number":
            raw = entry.get("value_number")
            if raw in (None, ""):
                ans.value_number = None
            else:
                try:
                    ans.value_number = Decimal(str(raw))
                except (InvalidOperation, ValueError):
                    return _api_error(
                        "validation_error", f"Неверное число для item_id={item_id}", 400
                    )
        else:
            ans.value_text = (entry.get("value_text") or "").strip()
        if "media_id" in entry:
            ans.media_id = entry.get("media_id")
        ans.answered_by_user_id = current_user.id
        ans.answered_at = datetime.utcnow()
        updated += 1

    db.session.commit()
    state = get_checklist_completion_state(req)
    return jsonify({"ok": True, "updated": updated, "state": state}), 200
