import json
import os
import re
import shutil
import uuid
from datetime import date, datetime, timedelta
from io import BytesIO
from urllib.parse import urlparse

import pandas as pd
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.all_models import (
    Client,
    Contract,
    ContractDocument,
    Equipment,
    Request,
    RequestStatus,
)
from app.modules.contracts import services as contract_services
from app.utils import contract_wizard as cw

contracts_bp = Blueprint("contracts", __name__)

# Ключи для поля document_kind у ContractDocument
CONTRACT_DOCUMENT_KIND_OPTIONS = (
    ("signed", "Подписанный договор / скан"),
    ("appendix", "Приложение"),
    ("act", "Акт"),
    ("photo", "Фото объекта"),
    ("other", "Другое"),
    ("equipment_passport", "Паспорт оборудования"),
    ("equipment_cert", "Сертификат соответствия"),
    ("equipment_photo", "Фото оборудования"),
    ("equipment_act", "Акт предыдущего обслуживания"),
    ("equipment_other", "Иной файл по оборудованию"),
)


def _safe_next_url(default_url):
    raw = (request.args.get("next") if request.method == "GET" else request.form.get("next")) or ""
    raw = raw.strip()
    if raw and raw.startswith("/"):
        parsed = urlparse(raw)
        if not parsed.scheme and not parsed.netloc:
            return raw
    return default_url


def _request_status_value(req):
    if req.status is None:
        return ""
    return req.status.value if hasattr(req.status, "value") else str(req.status)


def _request_type_value(req):
    base_type = (req.type or "").strip().lower()
    if base_type:
        return base_type
    if req.service_type is None:
        return ""
    return req.service_type.value if hasattr(req.service_type, "value") else str(req.service_type)


def _normalize_scope_items(raw_scope):
    if not raw_scope:
        return []
    try:
        payload = json.loads(raw_scope)
    except Exception:
        return []
    if not isinstance(payload, list):
        return []

    items = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        service_kind = str(entry.get("service_kind") or "").strip()
        planned_date = str(entry.get("planned_date") or "").strip()
        if not name or not planned_date:
            continue
        try:
            price = float(entry.get("price") or 0)
        except Exception:
            price = 0.0
        items.append(
            {
                "uid": str(entry.get("uid") or "").strip() or uuid.uuid4().hex,
                "name": name,
                "service_kind": service_kind,
                "planned_date": planned_date,
                "price": round(price, 2),
                "done_manual": bool(entry.get("done_manual")),
                "request_id": int(entry.get("request_id") or 0) or None,
            }
        )
    return items


def _scope_items_total(items):
    if not items:
        return 0.0
    return round(sum(float(i.get("price") or 0) for i in items), 2)


def _parse_price_mode(raw):
    v = (raw or "manual").strip().lower()
    return v if v in ("manual", "from_scope") else "manual"


def _apply_total_from_scope(contract):
    """Если режим from_scope — пересчитать total_price из JSON перечня."""
    items = _normalize_scope_items(contract.equipment_scope)
    contract.total_price = float(_scope_items_total(items))


def _scope_progress(items, requests):
    if not items:
        return {"planned_total": 0, "planned_closed": 0, "planned_percent": 0.0}

    closed_dates = {
        req.planned_date.isoformat()
        for req in requests
        if req.planned_date and _request_status_value(req) == "closed"
    }
    planned_total = len(items)
    planned_closed = 0
    for item in items:
        if item.get("done_manual") or item["planned_date"] in closed_dates:
            planned_closed += 1
    planned_percent = (planned_closed / planned_total * 100.0) if planned_total else 0.0
    return {
        "planned_total": planned_total,
        "planned_closed": planned_closed,
        "planned_percent": planned_percent,
    }


SCOPE_MARKER = "{{SCOPE_TABLE}}"


def _split_term_note(term_note):
    text = (term_note or "").strip()
    if not text:
        return "", "", False
    if SCOPE_MARKER in text:
        before, after = text.split(SCOPE_MARKER, 1)
        return before.strip(), after.strip(), True
    return text, "", False


def _sync_scope_rows_to_requests(contract, rows):
    rows_by_uid = {row["uid"]: row for row in rows if row.get("uid")}
    existing = {
        req.contract_scope_uid: req
        for req in Request.query.filter(
            Request.contract_id == contract.id,
            Request.contract_scope_uid.isnot(None),
        ).all()
    }

    created_count = 0
    updated_count = 0
    archived_count = 0

    for uid, row in rows_by_uid.items():
        req = existing.get(uid)
        row_date = None
        try:
            row_date = datetime.strptime(row["planned_date"], "%Y-%m-%d").date()
        except Exception:
            pass
        req_type = "плановая"
        description = f"План ТО по договору #{contract.id}: {row['name']}"
        if row.get("service_kind"):
            description += f" ({row['service_kind']})"

        if req is None:
            req = Request(
                client_id=contract.client_id,
                contract_id=contract.id,
                contract_scope_uid=uid,
                type=req_type,
                description=description,
                planned_date=row_date,
                total_price=row.get("price") or 0,
                contract_regulated_price=row.get("price") or 0,
                status=RequestStatus.assigned,
            )
            db.session.add(req)
            db.session.flush()
            req.request_number = f"REQ-{req.id:06d}"
            created_count += 1
        else:
            if req.status != RequestStatus.closed:
                req.client_id = contract.client_id
                req.contract_id = contract.id
                req.type = req_type
                req.description = description
                req.planned_date = row_date
                req.total_price = row.get("price") or 0
                req.contract_regulated_price = row.get("price") or 0
                updated_count += 1

        row["request_id"] = req.id

    for uid, req in existing.items():
        if uid not in rows_by_uid and req.status != RequestStatus.closed:
            req.status = RequestStatus.cancelled
            archived_count += 1

    return created_count, updated_count, archived_count, list(rows_by_uid.values())


def _scope_sync_preview(contract, rows):
    return contract_services.scope_sync_preview(contract, rows)


def _wizard_view_model(contract):
    return contract_services.wizard_view_model(contract)


def _build_contract_view_context(
    contract, active_tab, back_url, preview_sync=None, scope_items_override=None
):
    today = date.today()
    all_requests = sorted(
        contract.requests or [], key=lambda r: r.planned_date or date.min, reverse=True
    )
    emergency_requests = [
        r for r in all_requests if _request_type_value(r) in {"аварийная", "emergency"}
    ]
    planned_requests = [
        r for r in all_requests if _request_type_value(r) in {"плановая", "planned"}
    ]
    overdue_planned = [
        r
        for r in planned_requests
        if r.planned_date
        and r.planned_date < today
        and _request_status_value(r) not in {"closed", "cancelled"}
    ]
    emergency_cost_fact = sum(
        float(r.total_price or r.urgent_price or 0) for r in emergency_requests
    )
    scope_items = (
        scope_items_override
        if scope_items_override is not None
        else _normalize_scope_items(contract.equipment_scope)
    )
    scope_total = _scope_items_total(scope_items)
    progress = _scope_progress(scope_items, all_requests)
    term_before, term_after, include_scope = _split_term_note(contract.term_note)
    template_names = contract_services.template_names()
    wizard_view = _wizard_view_model(contract)
    return {
        "contract": contract,
        "today": today,
        "all_requests": all_requests,
        "emergency_requests": emergency_requests,
        "planned_requests": planned_requests,
        "overdue_planned": overdue_planned,
        "emergency_cost_fact": emergency_cost_fact,
        "scope_items": scope_items,
        "scope_progress": progress,
        "scope_total": scope_total,
        "template_names": template_names,
        "active_tab": active_tab,
        "term_before": term_before,
        "term_after": term_after,
        "include_scope": include_scope,
        "scope_marker": SCOPE_MARKER,
        "back_url": back_url,
        "preview_sync": preview_sync,
        "wizard_view": wizard_view,
        "contract_doc_kind_options": CONTRACT_DOCUMENT_KIND_OPTIONS,
        "contract_doc_kind_labels": dict(CONTRACT_DOCUMENT_KIND_OPTIONS),
    }


def _scope_rows_from_wizard_contract(contract):
    return contract_services.scope_rows_from_wizard_contract(contract)


@contracts_bp.route("/", methods=["GET"])
@contracts_bp.route("/list", methods=["GET"])
@login_required
def list_contracts():
    if current_user.role != "admin":
        flash("Раздел договоров доступен только администратору.", "danger")
        return redirect(url_for("requests.list_requests"))

    today = date.today()
    selected_year = request.args.get("year", type=int) or today.year
    contract_state = (request.args.get("contract_state") or "all").strip().lower()
    if contract_state not in {"all", "active", "expired"}:
        contract_state = "all"
    only_issues = (request.args.get("only_issues") or "").strip() in {"1", "true", "on", "yes"}
    only_overdue_totr = (request.args.get("only_overdue_totr") or "").strip() in {
        "1",
        "true",
        "on",
        "yes",
    }
    reminder_horizon = today + timedelta(days=30)

    rows, summary = _build_contract_report(selected_year, today, reminder_horizon)
    if only_overdue_totr:
        rows = [row for row in rows if row.get("overdue_equipment_count", 0) > 0]
    elif only_issues:
        rows = [
            row
            for row in rows
            if (
                row.get("overdue_equipment_count", 0) > 0 or row.get("overdue_planned_count", 0) > 0
            )
        ]
    if contract_state == "active":
        rows = [
            row
            for row in rows
            if row["contract"].end_date and row["contract"].end_date.date() >= today
        ]
    elif contract_state == "expired":
        rows = [
            row
            for row in rows
            if row["contract"].end_date and row["contract"].end_date.date() < today
        ]
    filtered_count = len(rows)
    return render_template(
        "contracts/list.html",
        rows=rows,
        selected_year=selected_year,
        contract_state=contract_state,
        only_issues=only_issues,
        only_overdue_totr=only_overdue_totr,
        filtered_count=filtered_count,
        summary=summary,
    )


@contracts_bp.route("/<int:contract_id>/edit", methods=["GET", "POST"])
@login_required
def edit_contract(contract_id):
    """Legacy endpoint: редирект в мастер договора."""
    if current_user.role != "admin":
        flash("Редактирование договора доступно только администратору.", "danger")
        return redirect(url_for("requests.list_requests"))

    flash("Старая форма отключена. Используйте мастер договора.", "info")
    return redirect(url_for("contracts.edit_contract_wizard", contract_id=contract_id))


@contracts_bp.route("/<int:contract_id>", methods=["GET"])
@login_required
def view_contract(contract_id):
    if current_user.role != "admin":
        flash("Карточка договора доступна только администратору.", "danger")
        return redirect(url_for("requests.list_requests"))

    contract = Contract.query.options(
        joinedload(Contract.client),
        joinedload(Contract.documents),
        joinedload(Contract.equipments),
    ).get_or_404(contract_id)

    active_tab = (request.args.get("tab") or "overview").strip().lower()
    if active_tab == "equipment":
        active_tab = "scope"
    if active_tab not in {"overview", "terms", "scope", "docs", "requests"}:
        active_tab = "overview"

    back_url = _safe_next_url(url_for("contracts.list_contracts"))
    ctx = _build_contract_view_context(contract, active_tab=active_tab, back_url=back_url)
    return render_template("contracts/view.html", **ctx)


@contracts_bp.route("/<int:contract_id>/delete", methods=["POST"])
@login_required
def delete_contract(contract_id):
    if current_user.role != "admin":
        flash("Удаление договора доступно только администратору.", "danger")
        return redirect(url_for("requests.list_requests"))

    contract = Contract.query.get_or_404(contract_id)
    client_id = contract.client_id
    doc_upload_dir = os.path.join("app", "static", "uploads", "contracts", str(contract.id))

    reqs = Request.query.filter(Request.contract_id == contract.id).all()
    for req in reqs:
        if req.status != RequestStatus.closed:
            req.status = RequestStatus.cancelled
        req.contract_id = None
        req.contract_scope_uid = None
        req.contract_regulated_price = None

    adapters = current_app.extensions.get("contracts_module", {}).get("adapters")
    if adapters:
        adapters.equipment.detach_by_contract_id(contract.id)
    else:
        Equipment.query.filter(Equipment.contract_id == contract.id).update(
            {Equipment.contract_id: None},
            synchronize_session=False,
        )

    db.session.delete(contract)
    db.session.commit()

    try:
        shutil.rmtree(doc_upload_dir, ignore_errors=True)
    except Exception:
        pass

    flash(
        "Договор удален. Связанные заявки отвязаны, незакрытые переведены в отмененные.", "success"
    )
    return redirect(url_for("clients.client_detail", client_id=client_id, tab="contracts"))


@contracts_bp.route("/<int:contract_id>/documents/upload", methods=["POST"])
@login_required
def upload_contract_document(contract_id):
    if current_user.role != "admin":
        flash("Загрузка документов доступна только администратору.", "danger")
        return redirect(url_for("contracts.view_contract", contract_id=contract_id))

    contract = Contract.query.get_or_404(contract_id)
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Выберите файл для загрузки.", "warning")
        return redirect(url_for("contracts.view_contract", contract_id=contract.id))

    upload_dir = os.path.join("app", "static", "uploads", "contracts", str(contract.id))
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = secure_filename(file.filename)
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    disk_name = f"{stamp}_{safe_name}" if safe_name else f"{stamp}.bin"
    abs_path = os.path.join(upload_dir, disk_name)
    file.save(abs_path)
    web_path = f"uploads/contracts/{contract.id}/{disk_name}"

    kind = (request.form.get("document_kind") or "").strip() or None
    if kind and len(kind) > 32:
        kind = kind[:32]

    doc = ContractDocument(
        contract_id=contract.id,
        title=(request.form.get("title") or "").strip() or safe_name,
        document_kind=kind,
        file_path=web_path,
        content_type=file.mimetype,
        uploaded_by_user_id=current_user.id,
    )
    db.session.add(doc)
    db.session.commit()
    flash("Документ договора загружен.", "success")
    return redirect(url_for("contracts.view_contract", contract_id=contract.id, tab="docs"))


@contracts_bp.route("/<int:contract_id>/terms/update", methods=["POST"])
@login_required
def update_contract_terms(contract_id):
    if current_user.role != "admin":
        flash("Редактирование условий доступно только администратору.", "danger")
        return redirect(url_for("contracts.view_contract", contract_id=contract_id))

    contract = Contract.query.get_or_404(contract_id)
    term_note = (request.form.get("term_note") or "").strip()
    equipment_scope = (request.form.get("equipment_scope") or "").strip()
    equipment_scope_json = (request.form.get("equipment_scope_json") or "").strip()
    return_tab = (request.form.get("return_tab") or "terms").strip().lower()
    action = (request.form.get("action") or "save").strip().lower()

    text_file = request.files.get("term_file")
    if text_file and text_file.filename:
        if not text_file.filename.lower().endswith(".txt"):
            flash("Для поля 'Условия' поддерживается только .txt файл.", "warning")
            return redirect(url_for("contracts.view_contract", contract_id=contract.id))
        raw = text_file.read()
        decoded_text = None
        for enc in ("utf-8", "cp1251", "windows-1251"):
            try:
                decoded_text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if decoded_text is None:
            flash(
                "Не удалось прочитать текстовый файл. Сохраните его в UTF-8 или CP1251.", "danger"
            )
            return redirect(url_for("contracts.view_contract", contract_id=contract.id))
        term_note = decoded_text.strip()

    parsed_scope = _normalize_scope_items(equipment_scope_json) if equipment_scope_json else []
    if return_tab == "scope" and not parsed_scope and contract.maintenance_wizard_json:
        parsed_scope = _scope_rows_from_wizard_contract(contract)

    if return_tab == "scope":
        if action == "preview":
            preview = _scope_sync_preview(contract, parsed_scope)
            back_url = _safe_next_url(url_for("contracts.list_contracts"))
            ctx = _build_contract_view_context(
                contract,
                active_tab="scope",
                back_url=back_url,
                preview_sync=preview,
                scope_items_override=parsed_scope,
            )
            return render_template("contracts/view.html", **ctx)

        created_count, updated_count, archived_count, synced_rows = _sync_scope_rows_to_requests(
            contract, parsed_scope
        )
        contract.equipment_scope = (
            json.dumps(synced_rows, ensure_ascii=False)
            if synced_rows
            else (equipment_scope or None)
        )
        if getattr(contract, "price_mode", None) == "from_scope":
            _apply_total_from_scope(contract)
        if action in {"sync", "sync_confirm"}:
            flash(
                f"Синхронизация выполнена: добавлено {created_count}, обновлено {updated_count}, отменено {archived_count}.",
                "success",
            )
        else:
            flash(
                f"Перечень сохранен и синхронизирован: добавлено {created_count}, обновлено {updated_count}, отменено {archived_count}.",
                "success",
            )
    else:
        term_before = (request.form.get("term_note_before") or "").strip()
        term_after = (request.form.get("term_note_after") or "").strip()
        include_scope = (request.form.get("include_scope") or "") in {"1", "on", "true", "yes"}

        parts = []
        if term_before:
            parts.append(term_before)
        if include_scope:
            parts.append(SCOPE_MARKER)
        if term_after:
            parts.append(term_after)
        if not parts and term_note:
            parts.append(term_note)
        contract.term_note = "\n\n".join(parts) if parts else None
        contract.service_periodicity = None
    db.session.commit()
    if return_tab != "scope":
        flash("Условия договора сохранены.", "success")
    return redirect(url_for("contracts.view_contract", contract_id=contract.id, tab=return_tab))


def _build_contract_report(selected_year, today, reminder_horizon):
    contracts = (
        Contract.query.options(joinedload(Contract.client))
        .order_by(Contract.end_date.desc().nullslast(), Contract.id.desc())
        .all()
    )

    rows = []
    total_planned = 0
    total_planned_closed = 0
    total_all_requests = 0
    total_emergency = 0
    total_unplanned_repair = 0
    total_extra_money = 0.0
    total_upcoming = 0

    for contract in contracts:
        contract_requests = [
            req
            for req in (contract.requests or [])
            if req.planned_date and req.planned_date.year == selected_year
        ]

        progress = _scope_progress(
            _normalize_scope_items(contract.equipment_scope), contract.requests or []
        )
        planned_total = progress["planned_total"]
        planned_closed = progress["planned_closed"]
        emergency_count = 0
        unplanned_repair_count = 0
        extra_money = 0.0

        for req in contract_requests:
            req_type = _request_type_value(req)
            status_val = _request_status_value(req)
            req_sum = float(req.total_price or req.urgent_price or 0)

            is_planned = req_type in {"плановая", "planned"}
            is_emergency = req_type in {"аварийная", "emergency"}
            is_repair = req_type in {"ремонтная", "repair"}

            if not is_planned:
                # Любая не плановая заявка считается "дополнительной" по деньгам.
                extra_money += req_sum

            if is_emergency:
                emergency_count += 1
            if is_repair:
                unplanned_repair_count += 1

        # Если перечень не заполнен таблицей, fallback на старую логику по плановым заявкам.
        if planned_total == 0:
            for req in contract_requests:
                req_type = _request_type_value(req)
                status_val = _request_status_value(req)
                if req_type in {"плановая", "planned"}:
                    planned_total += 1
                    if status_val == "closed":
                        planned_closed += 1

        planned_percent = (planned_closed / planned_total * 100.0) if planned_total else 0.0

        equipment_by_contract = (
            Equipment.query.filter(
                Equipment.contract_id == contract.id,
                Equipment.next_service_date.isnot(None),
            )
            .order_by(Equipment.next_service_date.asc())
            .all()
        )
        upcoming_equipment = [
            e
            for e in equipment_by_contract
            if e.next_service_date and today <= e.next_service_date <= reminder_horizon
        ]

        rows.append(
            {
                "contract": contract,
                "planned_total": planned_total,
                "planned_closed": planned_closed,
                "planned_percent": planned_percent,
                "all_requests": len(contract_requests),
                "emergency_count": emergency_count,
                "unplanned_repair_count": unplanned_repair_count,
                "extra_money": extra_money,
                "upcoming_equipment": upcoming_equipment[:5],
                "upcoming_count": len(upcoming_equipment),
                "overdue_equipment_count": len(
                    [
                        e
                        for e in equipment_by_contract
                        if e.next_service_date and e.next_service_date < today
                    ]
                ),
                "overdue_planned_count": len(
                    [
                        req
                        for req in contract.requests or []
                        if req.planned_date
                        and req.planned_date < today
                        and _request_type_value(req) in {"плановая", "planned"}
                        and _request_status_value(req) not in {"closed", "cancelled"}
                    ]
                ),
            }
        )

        total_planned += planned_total
        total_planned_closed += planned_closed
        total_all_requests += len(contract_requests)
        total_emergency += emergency_count
        total_unplanned_repair += unplanned_repair_count
        total_extra_money += extra_money
        total_upcoming += len(upcoming_equipment)

    total_planned_percent = (total_planned_closed / total_planned * 100.0) if total_planned else 0.0

    summary = {
        "contracts": len(contracts),
        "planned_total": total_planned,
        "planned_closed": total_planned_closed,
        "planned_percent": total_planned_percent,
        "all_requests": total_all_requests,
        "emergency": total_emergency,
        "unplanned_repair": total_unplanned_repair,
        "extra_money": total_extra_money,
        "upcoming": total_upcoming,
    }
    return rows, summary


@contracts_bp.route("/export", methods=["GET"])
@login_required
def export_contracts():
    if current_user.role != "admin":
        flash("Экспорт договоров доступен только администратору.", "danger")
        return redirect(url_for("requests.list_requests"))

    today = date.today()
    selected_year = request.args.get("year", type=int) or today.year
    reminder_horizon = today + timedelta(days=30)
    rows, _summary = _build_contract_report(selected_year, today, reminder_horizon)

    data = []
    for row in rows:
        c = row["contract"]
        data.append(
            {
                "contract_id": c.id,
                "client_id": c.client_id,
                "client_name": c.client.full_name if c.client else "",
                "contract_type": c.contract_type or "",
                "document_number": getattr(c, "document_number", None) or "",
                "price_mode": getattr(c, "price_mode", None) or "manual",
                "total_price": c.total_price or 0,
                "emergency_included_count": c.emergency_included_count
                if c.emergency_included_count is not None
                else "",
                "emergency_included_cost": float(c.emergency_included_cost)
                if c.emergency_included_cost is not None
                else "",
                "start_date": c.start_date.date().isoformat() if c.start_date else "",
                "end_date": c.end_date.date().isoformat() if c.end_date else "",
                "counterparty_kind": c.counterparty_kind or "",
                "conclusion_date": c.conclusion_date.isoformat() if c.conclusion_date else "",
                "service_periodicity": c.service_periodicity or "",
                "equipment_scope": c.equipment_scope or "",
                "planned_total": row["planned_total"],
                "planned_closed": row["planned_closed"],
                "planned_percent": round(row["planned_percent"], 2),
                "all_requests": row["all_requests"],
                "emergency_count": row["emergency_count"],
                "unplanned_repair_count": row["unplanned_repair_count"],
                "extra_money": round(row["extra_money"], 2),
                "upcoming_totr_count": row["upcoming_count"],
            }
        )

    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"contracts_report_{selected_year}.xlsx",
    )


def _safe_str(value):
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _parse_date_or_none(value):
    raw = _safe_str(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


@contracts_bp.route("/import", methods=["POST"])
@login_required
def import_contracts():
    if current_user.role != "admin":
        flash("Импорт договоров доступен только администратору.", "danger")
        return redirect(url_for("requests.list_requests"))

    file = request.files.get("file")
    if not file or not file.filename:
        flash("Выберите файл Excel для импорта.", "warning")
        return redirect(url_for("contracts.list_contracts"))
    if not file.filename.lower().endswith(".xlsx"):
        flash("Поддерживается только формат .xlsx.", "danger")
        return redirect(url_for("contracts.list_contracts"))

    try:
        df = pd.read_excel(file)
    except Exception:
        flash("Не удалось прочитать Excel файл.", "danger")
        return redirect(url_for("contracts.list_contracts"))

    column_map = {
        "ID договора": "contract_id",
        "contract_id": "contract_id",
        "ID клиента": "client_id",
        "client_id": "client_id",
        "Тип договора": "contract_type",
        "contract_type": "contract_type",
        "Сумма договора": "total_price",
        "total_price": "total_price",
        "Аварийных в лимите": "emergency_included_count",
        "emergency_included_count": "emergency_included_count",
        "Стоимость аварийных в лимите": "emergency_included_cost",
        "emergency_included_cost": "emergency_included_cost",
        "Дата начала": "start_date",
        "start_date": "start_date",
        "Дата окончания": "end_date",
        "end_date": "end_date",
        "counterparty_kind": "counterparty_kind",
        "conclusion_date": "conclusion_date",
        "service_periodicity": "service_periodicity",
        "equipment_scope": "equipment_scope",
        "Номер договора": "document_number",
        "document_number": "document_number",
        "Режим суммы": "price_mode",
        "price_mode": "price_mode",
    }
    df.rename(columns=column_map, inplace=True)

    imported = 0
    updated = 0
    skipped = 0

    for _idx, row in df.iterrows():
        contract_id_raw = row.get("contract_id")
        client_id_raw = row.get("client_id")
        contract_type = _safe_str(row.get("contract_type"))
        total_price_raw = row.get("total_price")
        emergency_included_count_raw = row.get("emergency_included_count")
        emergency_included_cost_raw = row.get("emergency_included_cost")
        start_date = _parse_date_or_none(row.get("start_date"))
        end_date = _parse_date_or_none(row.get("end_date"))

        try:
            contract_id = int(contract_id_raw) if not pd.isna(contract_id_raw) else None
        except Exception:
            contract_id = None
        try:
            client_id = int(client_id_raw) if not pd.isna(client_id_raw) else None
        except Exception:
            client_id = None

        if not client_id and contract_id:
            existing = Contract.query.get(contract_id)
            client_id = existing.client_id if existing else None

        if not client_id or not contract_type:
            skipped += 1
            continue

        client = Client.query.get(client_id)
        if not client:
            skipped += 1
            continue

        try:
            total_price = (
                float(total_price_raw)
                if total_price_raw is not None and not pd.isna(total_price_raw)
                else 0.0
            )
        except Exception:
            total_price = 0.0
        try:
            emergency_included_count = (
                int(emergency_included_count_raw)
                if emergency_included_count_raw is not None
                and not pd.isna(emergency_included_count_raw)
                else None
            )
        except Exception:
            emergency_included_count = None
        try:
            emergency_included_cost = (
                float(emergency_included_cost_raw)
                if emergency_included_cost_raw is not None
                and not pd.isna(emergency_included_cost_raw)
                else None
            )
        except Exception:
            emergency_included_cost = None

        contract = Contract.query.get(contract_id) if contract_id else None
        if contract:
            updated += 1
        else:
            contract = Contract(client_id=client_id)
            db.session.add(contract)
            imported += 1

        contract.client_id = client_id
        contract.contract_type = contract_type
        contract.total_price = total_price
        contract.emergency_included_count = emergency_included_count
        contract.emergency_included_cost = emergency_included_cost
        contract.start_date = (
            datetime.combine(start_date, datetime.min.time()) if start_date else None
        )
        contract.end_date = datetime.combine(end_date, datetime.min.time()) if end_date else None
        contract.counterparty_kind = _safe_str(row.get("counterparty_kind")) or None
        contract.conclusion_date = _parse_date_or_none(row.get("conclusion_date"))
        contract.service_periodicity = _safe_str(row.get("service_periodicity")) or None
        contract.equipment_scope = _safe_str(row.get("equipment_scope")) or None
        dn = _safe_str(row.get("document_number"))
        contract.document_number = dn or None
        pm = _safe_str(row.get("price_mode")).lower()
        if pm in ("manual", "from_scope"):
            contract.price_mode = pm
        if contract.price_mode == "from_scope":
            _apply_total_from_scope(contract)

    db.session.commit()
    flash(
        f"Импорт завершен: добавлено {imported}, обновлено {updated}, пропущено {skipped}.",
        "success",
    )
    return redirect(url_for("contracts.list_contracts"))


WIZARD_UPLOAD_KIND_MAP = {
    "passport": "equipment_passport",
    "cert": "equipment_cert",
    "photo": "equipment_photo",
    "act": "equipment_act",
    "other": "equipment_other",
}


def _wizard_file_pat():
    return re.compile(r"^eq_(\d+)_(passport|cert|photo|act|other)$")


def _store_wizard_uploads(contract, titles_by_idx):
    """Сохраняет файлы из мастера: поля eq_{i}_{kind}."""
    pat = _wizard_file_pat()
    upload_dir = os.path.join("app", "static", "uploads", "contracts", str(contract.id))
    os.makedirs(upload_dir, exist_ok=True)
    for key in request.files:
        m = pat.match(key)
        if not m:
            continue
        idx = int(m.group(1))
        slot = m.group(2)
        kind = WIZARD_UPLOAD_KIND_MAP.get(slot)
        if not kind:
            continue
        label = (titles_by_idx.get(idx) or f"Оборудование {idx + 1}").strip()
        prefix = {
            "passport": "Паспорт",
            "cert": "Сертификат",
            "photo": "Фото",
            "act": "Акт",
            "other": "Файл",
        }.get(slot, "Файл")
        for file in request.files.getlist(key):
            if not file or not file.filename:
                continue
            safe_name = secure_filename(file.filename)
            stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
            disk_name = f"{stamp}_{safe_name}" if safe_name else f"{stamp}.bin"
            abs_path = os.path.join(upload_dir, disk_name)
            file.save(abs_path)
            web_path = f"uploads/contracts/{contract.id}/{disk_name}"
            doc = ContractDocument(
                contract_id=contract.id,
                title=f"{prefix}: {label}"[:255],
                document_kind=kind,
                file_path=web_path,
                content_type=file.mimetype,
                uploaded_by_user_id=current_user.id,
            )
            db.session.add(doc)


def _apply_wizard_to_contract(contract, wizard, *, save_mode: str, sync_requests_flag: bool):
    """Заполняет договор из JSON мастера и при необходимости синхронизирует заявки."""
    c = wizard.get("contract") or {}
    contract_type = (c.get("contract_type") or "").strip() or "комплексный"
    contract.contract_type = contract_type
    contract.counterparty_kind = (wizard.get("counterparty_kind") or "").strip() or None
    cd = c.get("conclusion_date")
    if cd:
        try:
            contract.conclusion_date = datetime.strptime(str(cd)[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    sd, ed = cw.dates_from_wizard(wizard)
    if sd:
        contract.start_date = datetime.combine(sd, datetime.min.time())
    if ed:
        contract.end_date = datetime.combine(ed, datetime.min.time())
    dn = (c.get("document_number") or "").strip() or None
    contract.document_number = dn
    contract.term_note = (c.get("term_note") or "").strip() or None
    contract.service_periodicity = (
        "\n\n".join(
            x
            for x in (
                cw.merge_payment_terms_note(wizard),
                cw.build_service_periodicity_summary(wizard),
            )
            if x
        ).strip()
        or None
    )
    contract.maintenance_wizard_json = json.dumps(wizard, ensure_ascii=False)
    contract.price_mode = "from_scope"
    if save_mode == "draft":
        contract.equipment_scope = None
        contract.total_price = (
            float(cw.wizard_payload_total(wizard, sd, ed) if sd and ed else 0) or 0
        )
        return
    rows = cw.expand_wizard_to_scope_rows(wizard, sd, ed) if sd and ed else []
    contract.equipment_scope = json.dumps(rows, ensure_ascii=False) if rows else None
    if sync_requests_flag and rows:
        _created, _upd, _arch, synced = _sync_scope_rows_to_requests(contract, rows)
        contract.equipment_scope = json.dumps(synced, ensure_ascii=False) if synced else None
    _apply_total_from_scope(contract)


def _create_equipment_rows(contract, wizard, client_id):
    Equipment.query.filter(Equipment.contract_id == contract.id).delete(synchronize_session=False)
    for eq in wizard.get("equipment") or []:
        serial = (eq.get("serial") or "").strip() or f"WZ-{contract.id}-{uuid.uuid4().hex[:8]}"
        title = (eq.get("title") or "Узел").strip()[:50]
        e = Equipment(
            client_id=client_id,
            contract_id=contract.id,
            serial_number=serial[:50],
            type=title,
            kind=(eq.get("fuel") or "")[:50] if eq.get("fuel") else None,
            brand=(eq.get("brand") or "")[:50] if eq.get("brand") else None,
            model=(eq.get("model") or "")[:50] if eq.get("model") else None,
            production_year=int(eq["year"]) if eq.get("year") else None,
        )
        db.session.add(e)


@contracts_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_contract_wizard():
    if current_user.role != "admin":
        flash("Раздел договоров доступен только администратору.", "danger")
        return redirect(url_for("requests.list_requests"))

    if request.method == "GET":
        client_id = request.args.get("client_id", type=int)
        w = cw.default_wizard(client_id)
        if client_id:
            cl = Client.query.get(client_id)
            if cl:
                w["client_id"] = client_id
                w["counterparty_kind"] = getattr(cl, "client_kind", None) or ""
                snap = w["client_snapshot"]
                snap["legal_name"] = cl.full_name or ""
                snap["phone"] = cl.phone or ""
                snap["email"] = cl.email or ""
                snap["actual_address"] = cl.address or ""
                snap["legal_address"] = cl.address or ""
                snap["contact_person"] = cl.representative_name or ""
        return render_template(
            "contracts/wizard.html",
            wizard=w,
            contract=None,
            mode="create",
            client_id=client_id,
            work_kind_choices=list(cw.DEFAULT_WORK_KINDS.items()) + [("OTHER", "Другое (вручную)")],
            frequency_choices=cw.FREQUENCY_CHOICES,
            equipment_categories=list(cw.EQUIPMENT_CATEGORY_LABELS.items()),
            fuel_choices=cw.FUEL_OPTIONS,
            contract_doc_kind_labels=dict(CONTRACT_DOCUMENT_KIND_OPTIONS),
        )

    payload_raw = (request.form.get("wizard_payload") or "").strip()
    save_mode = (request.form.get("save_mode") or "final").strip().lower()
    try:
        wizard = json.loads(payload_raw) if payload_raw else {}
    except json.JSONDecodeError:
        flash("Некорректные данные формы. Попробуйте ещё раз.", "danger")
        return redirect(url_for("contracts.create_contract_wizard"))

    if not isinstance(wizard, dict):
        wizard = {}

    cif = request.form.get("client_id")
    if cif:
        try:
            wizard["client_id"] = int(cif)
        except (ValueError, TypeError):
            pass

    client_id = int(wizard.get("client_id") or 0) or None
    if not client_id:
        flash("Укажите заказчика.", "danger")
        return redirect(url_for("contracts.create_contract_wizard"))

    cl = Client.query.get(client_id)
    if not cl:
        flash("Клиент не найден.", "danger")
        return redirect(url_for("contracts.create_contract_wizard"))

    if save_mode == "final":
        errs = cw.validate_wizard_for_final(wizard)
        if errs:
            for e in errs[:6]:
                flash(e, "danger")
            return render_template(
                "contracts/wizard.html",
                wizard=wizard,
                contract=None,
                mode="create",
                client_id=client_id,
                work_kind_choices=list(cw.DEFAULT_WORK_KINDS.items())
                + [("OTHER", "Другое (вручную)")],
                frequency_choices=cw.FREQUENCY_CHOICES,
                equipment_categories=list(cw.EQUIPMENT_CATEGORY_LABELS.items()),
                fuel_choices=cw.FUEL_OPTIONS,
                contract_doc_kind_labels=dict(CONTRACT_DOCUMENT_KIND_OPTIONS),
            )

    contract = Contract(
        client_id=client_id,
        created_by_user_id=current_user.id,
        contract_type=(wizard.get("contract") or {}).get("contract_type") or "комплексный",
    )
    db.session.add(contract)
    db.session.flush()

    sync = save_mode == "final"
    _apply_wizard_to_contract(contract, wizard, save_mode=save_mode, sync_requests_flag=sync)
    if sync:
        _create_equipment_rows(contract, wizard, client_id)
    titles = {
        i: (eq.get("title") or f"Узел {i + 1}")
        for i, eq in enumerate(wizard.get("equipment") or [])
    }
    _store_wizard_uploads(contract, titles)
    if not (contract.document_number or "").strip():
        contract.document_number = f"ДГ-{date.today().year}-{contract.id}"
    db.session.commit()

    if save_mode == "draft":
        flash(
            "Черновик договора сохранён. Можно продолжить редактирование в карточке договора.",
            "success",
        )
    else:
        flash("Договор создан: перечень позиций и заявки сформированы по графику.", "success")
    return redirect(url_for("contracts.view_contract", contract_id=contract.id, tab="overview"))


@contracts_bp.route("/<int:contract_id>/wizard", methods=["GET", "POST"])
@login_required
def edit_contract_wizard(contract_id):
    if current_user.role != "admin":
        flash("Доступ только администратору.", "danger")
        return redirect(url_for("requests.list_requests"))

    contract = Contract.query.get_or_404(contract_id)

    if request.method == "GET":
        w = cw.parse_wizard_json(contract.maintenance_wizard_json) or cw.default_wizard(
            contract.client_id
        )
        w["client_id"] = contract.client_id
        if not w.get("contract"):
            w["contract"] = {}
        wc = w["contract"]
        wc.setdefault("contract_type", contract.contract_type or "комплексный")
        wc.setdefault("document_number", contract.document_number or "")
        wc.setdefault(
            "conclusion_date",
            contract.conclusion_date.isoformat() if contract.conclusion_date else "",
        )
        wc.setdefault(
            "start_date",
            contract.start_date.strftime("%Y-%m-%d") if contract.start_date else "",
        )
        wc.setdefault(
            "end_date", contract.end_date.strftime("%Y-%m-%d") if contract.end_date else ""
        )
        w["counterparty_kind"] = contract.counterparty_kind or ""
        return render_template(
            "contracts/wizard.html",
            wizard=w,
            contract=contract,
            mode="edit",
            client_id=contract.client_id,
            work_kind_choices=list(cw.DEFAULT_WORK_KINDS.items()) + [("OTHER", "Другое (вручную)")],
            frequency_choices=cw.FREQUENCY_CHOICES,
            equipment_categories=list(cw.EQUIPMENT_CATEGORY_LABELS.items()),
            fuel_choices=cw.FUEL_OPTIONS,
            contract_doc_kind_labels=dict(CONTRACT_DOCUMENT_KIND_OPTIONS),
        )

    payload_raw = (request.form.get("wizard_payload") or "").strip()
    save_mode = (request.form.get("save_mode") or "final").strip().lower()
    try:
        wizard = json.loads(payload_raw) if payload_raw else {}
    except json.JSONDecodeError:
        flash("Некорректные данные формы.", "danger")
        return redirect(url_for("contracts.edit_contract_wizard", contract_id=contract_id))

    wizard["client_id"] = contract.client_id
    cif = request.form.get("client_id")
    if cif:
        try:
            wizard["client_id"] = int(cif)
        except (ValueError, TypeError):
            pass

    if save_mode == "final":
        errs = cw.validate_wizard_for_final(wizard)
        if errs:
            for e in errs[:6]:
                flash(e, "danger")
            return render_template(
                "contracts/wizard.html",
                wizard=wizard,
                contract=contract,
                mode="edit",
                client_id=contract.client_id,
                work_kind_choices=list(cw.DEFAULT_WORK_KINDS.items())
                + [("OTHER", "Другое (вручную)")],
                frequency_choices=cw.FREQUENCY_CHOICES,
                equipment_categories=list(cw.EQUIPMENT_CATEGORY_LABELS.items()),
                fuel_choices=cw.FUEL_OPTIONS,
                contract_doc_kind_labels=dict(CONTRACT_DOCUMENT_KIND_OPTIONS),
            )

    sync = save_mode == "final"
    _apply_wizard_to_contract(contract, wizard, save_mode=save_mode, sync_requests_flag=sync)
    if sync:
        _create_equipment_rows(contract, wizard, contract.client_id)
    titles = {
        i: (eq.get("title") or f"Узел {i + 1}")
        for i, eq in enumerate(wizard.get("equipment") or [])
    }
    _store_wizard_uploads(contract, titles)
    db.session.commit()
    flash("Договор обновлён по мастеру.", "success")
    return redirect(url_for("contracts.view_contract", contract_id=contract.id, tab="overview"))
