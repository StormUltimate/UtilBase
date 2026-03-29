"""Сервисный слой модуля договоров.

Здесь хранится бизнес-логика, которую можно переиспользовать в других проектах.
"""

from __future__ import annotations

from flask import current_app

from app.models.all_models import EquipmentTemplate, Request, RequestStatus
from app.utils import contract_wizard as cw


def _adapters():
    ext = current_app.extensions.get("contracts_module", {})
    return ext.get("adapters")


def scope_sync_preview(contract, rows: list[dict]):
    """Предпросмотр синхронизации перечня в плановые заявки без записи в БД."""
    rows_by_uid = {row["uid"]: row for row in rows if row.get("uid")}
    adapters = _adapters()
    existing_rows = (
        adapters.requests.by_contract_scope(contract.id)
        if adapters
        else Request.query.filter(
            Request.contract_id == contract.id,
            Request.contract_scope_uid.isnot(None),
        ).all()
    )
    existing = {req.contract_scope_uid: req for req in existing_rows}

    created = []
    updated = []
    cancelled = []

    for uid, row in rows_by_uid.items():
        req = existing.get(uid)
        if req is None:
            created.append(row)
        elif req.status != RequestStatus.closed:
            updated.append(
                {
                    "uid": uid,
                    "name": row.get("name") or "",
                    "service_kind": row.get("service_kind") or "",
                    "planned_date": row.get("planned_date") or "",
                    "price": float(row.get("price") or 0),
                    "request_id": req.id,
                    "request_number": req.request_number or f"#{req.id}",
                }
            )

    for uid, req in existing.items():
        if uid not in rows_by_uid and req.status != RequestStatus.closed:
            cancelled.append(
                {
                    "uid": uid,
                    "request_id": req.id,
                    "request_number": req.request_number or f"#{req.id}",
                    "planned_date": req.planned_date.isoformat() if req.planned_date else "",
                    "description": req.description or "",
                }
            )

    created_sorted = sorted(
        created, key=lambda r: (r.get("planned_date") or "", r.get("name") or "")
    )
    updated_sorted = sorted(
        updated, key=lambda r: (r.get("planned_date") or "", r.get("name") or "")
    )
    cancelled_sorted = sorted(
        cancelled, key=lambda r: (r.get("planned_date") or "", r.get("request_id") or 0)
    )
    return {
        "created": created_sorted,
        "updated": updated_sorted,
        "cancelled": cancelled_sorted,
        "created_count": len(created_sorted),
        "updated_count": len(updated_sorted),
        "cancelled_count": len(cancelled_sorted),
    }


def scope_rows_from_wizard_contract(contract):
    wizard = cw.parse_wizard_json(getattr(contract, "maintenance_wizard_json", None))
    if not wizard:
        return []
    start, end = cw.dates_from_wizard(wizard)
    if not start or not end:
        return []
    return cw.expand_wizard_to_scope_rows(wizard, start, end)


def wizard_view_model(contract):
    wizard = cw.parse_wizard_json(getattr(contract, "maintenance_wizard_json", None))
    if not wizard:
        return None

    c = wizard.get("contract") or {}
    snap = wizard.get("client_snapshot") or {}
    start, end = cw.dates_from_wizard(wizard)
    fuel_labels = {k: v for k, v in cw.FUEL_OPTIONS}

    equipment_rows = []
    total_planned = 0
    for eq in wizard.get("equipment") or []:
        eq_name = (eq.get("title") or "Оборудование").strip()
        category_key = (eq.get("category") or "").strip()
        category_label = cw.EQUIPMENT_CATEGORY_LABELS.get(category_key, category_key or "—")
        fuel_key = (eq.get("fuel") or "").strip()
        work_lines = []
        for wl in eq.get("work_lines") or []:
            wk_code = (wl.get("work_kind") or "").strip()
            wk_custom = (wl.get("work_kind_custom") or "").strip()
            work_label = (
                wk_custom
                if (wk_code == "OTHER" and wk_custom)
                else cw.DEFAULT_WORK_KINDS.get(wk_code, wk_code)
            )
            line_start = cw._safe_parse_iso_date(wl.get("start_date")) or start
            schedule_dates: list = []
            if start and end and line_start:
                if line_start < start:
                    line_start = start
                if line_start <= end:
                    schedule_dates = [line_start]
            work_lines.append(
                {
                    "work_label": work_label or "—",
                    "price_per_visit": float(wl.get("price_per_visit") or 0),
                    "start_date": line_start.isoformat() if line_start else "",
                    "planned_count": len(schedule_dates),
                    "first_dates": [d.isoformat() for d in schedule_dates[:6]],
                }
            )
            total_planned += len(schedule_dates)

        equipment_rows.append(
            {
                "name": eq_name,
                "category_label": category_label,
                "serial": (eq.get("serial") or "").strip(),
                "year": eq.get("year"),
                "fuel_label": fuel_labels.get(fuel_key, fuel_key or "—"),
                "work_lines": work_lines,
            }
        )

    return {
        "present": True,
        "client_snapshot": snap,
        "service_object_address": (wizard.get("service_object_address") or "").strip(),
        "counterparty_kind": (wizard.get("counterparty_kind") or "").strip(),
        "payment_terms": (c.get("payment_terms") or "").strip(),
        "payment_terms_note": (c.get("payment_terms_note") or "").strip(),
        "equipment_rows": equipment_rows,
        "equipment_count": len(equipment_rows),
        "planned_total_count": total_planned,
    }


def template_names():
    adapters = _adapters()
    if adapters:
        return adapters.templates.distinct_template_names()
    names = [
        row[0]
        for row in EquipmentTemplate.query.with_entities(EquipmentTemplate.type.distinct())
        .filter(EquipmentTemplate.type.isnot(None))
        .all()
        if row[0]
    ]
    names.sort()
    return names
