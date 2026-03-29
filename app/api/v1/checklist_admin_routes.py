"""CRUD шаблонов чек-листа для ролей ядра."""

from __future__ import annotations

from datetime import datetime

from flask import jsonify, request
from flask_jwt_extended import current_user, jwt_required

from app.api.v1 import api_v1_bp
from app.extensions import db
from app.models.all_models import ChecklistTemplate, ChecklistTemplateItem


def _api_error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _can_manage_templates(user) -> bool:
    return bool(user and user.role in ("admin", "dispatcher", "engineer"))


def _template_to_dict(t: ChecklistTemplate):
    return {
        "id": t.id,
        "name": t.name,
        "equipment_type": t.equipment_type,
        "equipment_id": t.equipment_id,
        "is_default": bool(t.is_default),
        "is_active": bool(t.is_active),
        "created_by_user_id": t.created_by_user_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _item_to_dict(i: ChecklistTemplateItem):
    return {
        "id": i.id,
        "template_id": i.template_id,
        "title": i.title,
        "item_order": i.item_order,
        "is_required": bool(i.is_required),
        "item_type": i.item_type,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


@api_v1_bp.route("/checklist/templates", methods=["GET"])
@jwt_required()
def list_checklist_templates():
    if not _can_manage_templates(current_user):
        return _api_error("forbidden", "Недостаточно прав", 403)
    q = ChecklistTemplate.query
    equipment_type = (request.args.get("equipment_type") or "").strip()
    if equipment_type:
        q = q.filter(ChecklistTemplate.equipment_type == equipment_type)
    include_inactive = (request.args.get("include_inactive") or "").lower() in ("1", "true", "yes")
    if not include_inactive:
        q = q.filter(ChecklistTemplate.is_active.is_(True))
    rows = q.order_by(ChecklistTemplate.is_default.desc(), ChecklistTemplate.id.asc()).all()
    return jsonify({"items": [_template_to_dict(x) for x in rows]}), 200


@api_v1_bp.route("/checklist/templates", methods=["POST"])
@jwt_required()
def create_checklist_template():
    if not _can_manage_templates(current_user):
        return _api_error("forbidden", "Недостаточно прав", 403)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return _api_error("validation_error", "Поле name обязательно", 400)
    is_default = bool(data.get("is_default", False))
    if is_default:
        ChecklistTemplate.query.update({ChecklistTemplate.is_default: False})
    row = ChecklistTemplate(
        name=name,
        equipment_type=((data.get("equipment_type") or "").strip() or None),
        equipment_id=data.get("equipment_id"),
        is_default=is_default,
        is_active=bool(data.get("is_active", True)),
        created_by_user_id=current_user.id if current_user else None,
        created_at=datetime.utcnow(),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(_template_to_dict(row)), 201


@api_v1_bp.route("/checklist/templates/<int:template_id>", methods=["GET"])
@jwt_required()
def get_checklist_template_admin(template_id: int):
    if not _can_manage_templates(current_user):
        return _api_error("forbidden", "Недостаточно прав", 403)
    row = ChecklistTemplate.query.filter_by(id=template_id).first()
    if not row:
        return _api_error("not_found", "Шаблон не найден", 404)
    items = (
        ChecklistTemplateItem.query.filter_by(template_id=template_id)
        .order_by(ChecklistTemplateItem.item_order.asc(), ChecklistTemplateItem.id.asc())
        .all()
    )
    return jsonify(
        {"template": _template_to_dict(row), "items": [_item_to_dict(i) for i in items]}
    ), 200


@api_v1_bp.route("/checklist/templates/<int:template_id>", methods=["PATCH"])
@jwt_required()
def patch_checklist_template(template_id: int):
    if not _can_manage_templates(current_user):
        return _api_error("forbidden", "Недостаточно прав", 403)
    row = ChecklistTemplate.query.filter_by(id=template_id).first()
    if not row:
        return _api_error("not_found", "Шаблон не найден", 404)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        row.name = (data.get("name") or "").strip() or row.name
    if "equipment_type" in data:
        row.equipment_type = (data.get("equipment_type") or "").strip() or None
    if "equipment_id" in data:
        row.equipment_id = data.get("equipment_id")
    if "is_active" in data:
        row.is_active = bool(data.get("is_active"))
    if "is_default" in data and bool(data.get("is_default")):
        ChecklistTemplate.query.update({ChecklistTemplate.is_default: False})
        row.is_default = True
    elif "is_default" in data:
        row.is_default = bool(data.get("is_default"))
    row.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(_template_to_dict(row)), 200


@api_v1_bp.route("/checklist/templates/<int:template_id>", methods=["DELETE"])
@jwt_required()
def delete_checklist_template(template_id: int):
    if not _can_manage_templates(current_user):
        return _api_error("forbidden", "Недостаточно прав", 403)
    row = ChecklistTemplate.query.filter_by(id=template_id).first()
    if not row:
        return _api_error("not_found", "Шаблон не найден", 404)
    db.session.delete(row)
    db.session.commit()
    return jsonify({"ok": True}), 200


@api_v1_bp.route("/checklist/templates/<int:template_id>/items", methods=["POST"])
@jwt_required()
def create_checklist_template_item(template_id: int):
    if not _can_manage_templates(current_user):
        return _api_error("forbidden", "Недостаточно прав", 403)
    template = ChecklistTemplate.query.filter_by(id=template_id).first()
    if not template:
        return _api_error("not_found", "Шаблон не найден", 404)
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return _api_error("validation_error", "Поле title обязательно", 400)
    row = ChecklistTemplateItem(
        template_id=template_id,
        title=title,
        item_order=int(data.get("item_order") or 0),
        is_required=bool(data.get("is_required", True)),
        item_type=(data.get("item_type") or "boolean").strip() or "boolean",
        created_at=datetime.utcnow(),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(_item_to_dict(row)), 201


@api_v1_bp.route("/checklist/templates/<int:template_id>/items/<int:item_id>", methods=["PATCH"])
@jwt_required()
def patch_checklist_template_item(template_id: int, item_id: int):
    if not _can_manage_templates(current_user):
        return _api_error("forbidden", "Недостаточно прав", 403)
    row = ChecklistTemplateItem.query.filter_by(id=item_id, template_id=template_id).first()
    if not row:
        return _api_error("not_found", "Пункт не найден", 404)
    data = request.get_json(silent=True) or {}
    if "title" in data:
        row.title = (data.get("title") or "").strip() or row.title
    if "item_order" in data:
        row.item_order = int(data.get("item_order") or row.item_order or 0)
    if "is_required" in data:
        row.is_required = bool(data.get("is_required"))
    if "item_type" in data:
        row.item_type = (data.get("item_type") or row.item_type).strip() or row.item_type
    db.session.commit()
    return jsonify(_item_to_dict(row)), 200


@api_v1_bp.route("/checklist/templates/<int:template_id>/items/<int:item_id>", methods=["DELETE"])
@jwt_required()
def delete_checklist_template_item(template_id: int, item_id: int):
    if not _can_manage_templates(current_user):
        return _api_error("forbidden", "Недостаточно прав", 403)
    row = ChecklistTemplateItem.query.filter_by(id=item_id, template_id=template_id).first()
    if not row:
        return _api_error("not_found", "Пункт не найден", 404)
    db.session.delete(row)
    db.session.commit()
    return jsonify({"ok": True}), 200
