# Path: V:\UtilBase\app\blueprints\requests\routes.py
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, not_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.all_models import (
    ChecklistTemplate,
    Client,
    Contract,
    Equipment,
    Media,
    Request,
    RequestActionLog,
    RequestMode,
    RequestStatus,
    Users,
    VisitType,
    Worker,
    WorkerShift,
    WorkOrder,
)
from app.utils.client_queries import clients_to_json_results, search_clients_for_picker
from app.utils.request_calendar import (
    parse_fc_iso,
    planned_range_for_request,
    shift_layer_events_from_db,
)

from .forms import RequestForm

requests_bp = Blueprint("requests", __name__)
EXECUTOR_ROLES = ("master", "engineer")


def _safe_next_url(default_url):
    raw = (request.args.get("next") if request.method == "GET" else request.form.get("next")) or ""
    raw = raw.strip()
    if raw and raw.startswith("/"):
        parsed = urlparse(raw)
        if not parsed.scheme and not parsed.netloc:
            return raw
    return default_url


def _visit_type_from_choice(val) -> VisitType:
    if val == VisitType.survey.value:
        return VisitType.survey
    return VisitType.repair


def _request_visible_to_user(req: Request) -> bool:
    """admin — всё; инженер/мастер — свои назначения или заявка без исполнителей."""
    if current_user.role == "admin":
        return True
    if current_user.role not in ["engineer", "master"]:
        return False
    if not req.workers:
        return True
    return any(w.id == current_user.id for w in req.workers)


def _active_executor_workers_query():
    return (
        Worker.query.join(Users, Users.worker_id == Worker.id)
        .filter(Worker.is_active.is_(True), Users.role.in_(EXECUTOR_ROLES))
        .order_by(Worker.full_name)
    )


def _resolve_checklist_template_id_for_request(equipment_id, _req_type):
    """Приоритет: шаблон на конкретное оборудование -> default."""
    if equipment_id:
        t = (
            ChecklistTemplate.query.filter(
                ChecklistTemplate.is_active.is_(True),
                ChecklistTemplate.equipment_id == equipment_id,
            )
            .order_by(ChecklistTemplate.id.desc())
            .first()
        )
        if t:
            return t.id

    default_t = (
        ChecklistTemplate.query.filter(
            ChecklistTemplate.is_active.is_(True),
            ChecklistTemplate.is_default.is_(True),
        )
        .order_by(ChecklistTemplate.id.desc())
        .first()
    )
    if default_t:
        return default_t.id
    return None


def _fmt_duration_between(start_dt, end_dt):
    if not start_dt or not end_dt:
        return None
    delta = end_dt - start_dt
    total_minutes = int(max(0, delta.total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours} ч {minutes} мин"
    if hours:
        return f"{hours} ч"
    return f"{minutes} мин"


def _build_request_timeline(req: Request):
    timeline = []

    timeline.append(
        {
            "at": req.created_at,
            "title": "Заявка создана",
        }
    )

    if req.planned_date:
        timeline.append(
            {
                "at": req.planned_date,
                "title": f"Запланирована на {req.planned_date.strftime('%d.%m.%Y')}",
            }
        )

    assigned_at = None
    for log in sorted(req.action_logs or [], key=lambda x: x.created_at or datetime.min):
        if log.action == "take":
            assigned_at = log.created_at
            break
    if req.workers:
        timeline.append(
            {
                "at": assigned_at,
                "title": f"Назначен: {', '.join(w.full_name for w in req.workers)}",
            }
        )

    mode_logs = sorted(
        [
            log
            for log in (req.action_logs or [])
            if log.action == "mode_change"
            and log.new_mode in ("on_way", "arrived", "in_progress", "completed")
        ],
        key=lambda x: x.created_at or datetime.min,
    )

    first_mode_at = {}
    for log in mode_logs:
        first_mode_at.setdefault(log.new_mode, log.created_at)

    on_way_at = first_mode_at.get("on_way")
    arrived_at = first_mode_at.get("arrived")
    in_progress_at = first_mode_at.get("in_progress") or req.actual_start_time
    completed_at = first_mode_at.get("completed")

    if on_way_at:
        timeline.append({"at": on_way_at, "title": 'Нажато "В пути"'})
    if arrived_at:
        travel_time = _fmt_duration_between(on_way_at, arrived_at)
        title = 'Нажато "Прибыл"'
        if travel_time:
            title += f" (в пути: {travel_time})"
        timeline.append({"at": arrived_at, "title": title})
    if in_progress_at:
        timeline.append({"at": in_progress_at, "title": 'Нажато "Начать работу"'})
    if completed_at:
        work_time = _fmt_duration_between(in_progress_at, completed_at)
        title = 'Нажато "Работа завершена"'
        if work_time:
            title += f" (в работе: {work_time})"
        timeline.append({"at": completed_at, "title": title})

    closed_at = None
    for log in sorted(req.action_logs or [], key=lambda x: x.created_at or datetime.min):
        if log.action == "close" or log.new_status == RequestStatus.closed.value:
            closed_at = log.created_at
            break
    if not closed_at and req.status == RequestStatus.closed:
        closed_at = req.actual_end_time or req.updated_at
    if closed_at:
        timeline.append({"at": closed_at, "title": "Заявка закрыта"})

    def _timeline_key(item):
        at = item.get("at")
        if at is None:
            return datetime.min
        # В таймлайне могут смешиваться datetime и date (например, planned_date).
        # Приводим всё к datetime для корректной сортировки.
        if isinstance(at, date) and not isinstance(at, datetime):
            return datetime.combine(at, datetime.min.time())
        return at

    timeline.sort(key=_timeline_key)
    return timeline


@requests_bp.before_request
def sync_request_overdue_status():
    try:
        overdue_requests = Request.query.filter(
            Request.planned_date < date.today(),
            Request.status.notin_(
                [RequestStatus.closed, RequestStatus.overdue, RequestStatus.cancelled]
            ),
        ).all()
        for req in overdue_requests:
            req.status = RequestStatus.overdue
        if overdue_requests:
            db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f"Ошибка: {str(e)}", "danger")


@requests_bp.route("/")
@requests_bp.route("/list")
@login_required
def list_requests():
    filter_type = request.args.get("filter", "all")
    type_filter = request.args.get("type", "")
    status_filter = request.args.get("status", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    search_client = request.args.get("search", "").strip()

    try:
        base_query = Request.query
        total_query = Request.query
        if filter_type == "today":
            base_query = base_query.filter(
                func.date(Request.planned_date) == date.today(),
                Request.status.notin_([RequestStatus.closed, RequestStatus.cancelled]),
            )
        elif filter_type == "planned":
            base_query = base_query.filter(
                Request.planned_date > datetime.now(),
                Request.status.notin_([RequestStatus.closed, RequestStatus.cancelled]),
            )
        elif filter_type == "overdue":
            base_query = base_query.filter(Request.status == RequestStatus.overdue)
        elif filter_type == "closed":
            base_query = base_query.filter(Request.status == RequestStatus.closed)
        elif filter_type == "cancelled":
            base_query = base_query.filter(Request.status == RequestStatus.cancelled)
        elif filter_type == "everything":
            pass
        elif filter_type == "all":
            # По умолчанию показываем только активные заявки:
            # отменённые считаем эквивалентом закрытых (через отмену).
            base_query = base_query.filter(
                Request.status.notin_([RequestStatus.closed, RequestStatus.cancelled])
            )
        else:
            base_query = base_query.filter(
                Request.status.notin_([RequestStatus.closed, RequestStatus.cancelled])
            )

        if type_filter:
            type_map = {
                "emergency": ["аварийная", "emergency"],
                "repair": ["ремонтная", "repair"],
                "planned": ["плановая", "planned"],
            }
            if type_filter in type_map:
                base_query = base_query.filter(
                    or_(
                        Request.type.in_(type_map[type_filter]), Request.service_type == type_filter
                    )
                )

        if status_filter:
            try:
                base_query = base_query.filter(Request.status == RequestStatus(status_filter))
            except ValueError:
                pass

        if date_from:
            try:
                df = datetime.strptime(date_from, "%Y-%m-%d").date()
                base_query = base_query.filter(Request.planned_date >= df)
            except ValueError:
                pass
        if date_to:
            try:
                dt = datetime.strptime(date_to, "%Y-%m-%d").date()
                base_query = base_query.filter(Request.planned_date <= dt)
            except ValueError:
                pass

        if search_client:
            term = f"%{search_client}%"
            base_query = base_query.outerjoin(Client, Request.client_id == Client.id).filter(
                or_(
                    Client.full_name.ilike(term),
                    Client.address.ilike(term),
                    Client.phone.ilike(term),
                    Request.full_name.ilike(term),
                    Request.address.ilike(term),
                    Request.phone.ilike(term),
                )
            )

        if current_user.role in ["engineer", "master"]:
            visibility_filter = or_(
                Request.workers.any(id=current_user.id), not_(Request.workers.any())
            )
            base_query = base_query.filter(visibility_filter)
            total_query = total_query.filter(visibility_filter)

        requests = base_query.order_by(
            Request.planned_date.desc().nullslast(), Request.created_at.desc()
        ).all()
        total_requests = total_query.count()
        filtered_requests = len(requests)
        request_form = None
        if current_user.role == "admin":
            request_form = RequestForm(for_create=True)
            request_form.contract_id.choices = [(0, "Нет")] + [
                (c.id, c.contract_type or f"Договор #{c.id}") for c in Contract.query.all()
            ]
            request_form.equipment_id.choices = [(0, "Нет")] + [
                (e.id, e.model or e.serial_number or f"Оборудование #{e.id}")
                for e in Equipment.query.all()
            ]
            request_form.workers.choices = [
                (w.id, w.full_name) for w in _active_executor_workers_query().all()
            ]
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f"Ошибка: {str(e)}", "danger")
        requests = []
        total_requests = 0
        filtered_requests = 0
        request_form = None

    return render_template(
        "requests/list.html" if current_user.role == "admin" else "requests/list_mobile.html",
        requests=requests,
        filter=filter_type,
        type_filter=type_filter,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        search_client=search_client,
        total_requests=total_requests,
        filtered_requests=filtered_requests,
        request_form=request_form,
    )


@requests_bp.route("/today")
@login_required
def today_requests():
    if current_user.role != "admin":
        flash("Доступ только для админа.", "danger")
        return redirect(url_for("requests.list_requests"))

    filter_type = request.args.get("filter_type", "today")
    client_id = request.args.get("client_id")
    worker_id = request.args.get("worker_id")
    service_type = request.args.get("service_type")
    status = request.args.get("status")
    sort_by = request.args.get("sort_by", "planned_date")
    sort_order = request.args.get("sort_order", "asc")

    try:
        base_query = Request.query
        if filter_type == "today":
            base_query = base_query.filter(func.date(Request.planned_date) == date.today())
        elif filter_type == "overdue":
            base_query = base_query.filter(Request.status == RequestStatus.overdue)
        elif filter_type == "specific_date":
            specific_date = request.args.get("specific_date")
            if specific_date:
                base_query = base_query.filter(
                    func.date(Request.planned_date)
                    == datetime.strptime(specific_date, "%Y-%m-%d").date()
                )

        if client_id and client_id != "all":
            base_query = base_query.filter(Request.client_id == int(client_id))
        if worker_id and worker_id != "all":
            base_query = base_query.filter(Request.workers.any(id=int(worker_id)))
        if service_type and service_type != "all":
            base_query = base_query.filter(Request.service_type == service_type)
        if status and status != "all":
            base_query = base_query.filter(Request.status == status)

        if sort_by:
            order_col = getattr(Request, sort_by)
            if sort_order == "desc":
                order_col = order_col.desc()
            base_query = base_query.order_by(order_col)

        requests = base_query.all()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f"Ошибка: {str(e)}", "danger")
        requests = []

    clients = Client.query.all()
    workers = _active_executor_workers_query().all()
    tcid = request.args.get("client_id", "all")
    today_client_label = ""
    if tcid and tcid != "all":
        try:
            tc = Client.query.get(int(tcid))
            if tc:
                today_client_label = f"{tc.full_name or '—'} · {tc.phone or '—'}"
        except (ValueError, TypeError):
            pass
    return render_template(
        "requests/today.html",
        requests=requests,
        filter_type=filter_type,
        clients=clients,
        workers=workers,
        today_client_id=tcid,
        today_client_label=today_client_label,
    )


@requests_bp.route("/api/search_clients")
@login_required
def search_clients():
    q = request.args.get("query", "")
    kind = request.args.get("kind", "")
    rows = search_clients_for_picker(q, kind, limit=15)
    results = [{"id": r["id"], "text": r["text"]} for r in clients_to_json_results(rows)]
    return jsonify({"results": results})


@requests_bp.route("/api/get_client/<int:id>")
@login_required
def get_client(id):
    client = Client.query.get(id)
    if client:
        return jsonify(
            {"full_name": client.full_name, "address": client.address, "phone": client.phone}
        )
    return jsonify({}), 404


@requests_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_request():
    if current_user.role != "admin":
        flash("Доступ только для админа.", "danger")
        return redirect(url_for("requests.list_requests"))
    form = RequestForm(for_create=True)
    form.contract_id.choices = [(0, "Нет")] + [
        (c.id, c.contract_type) for c in Contract.query.all()
    ]
    form.equipment_id.choices = [(0, "Нет")] + [(e.id, e.model) for e in Equipment.query.all()]
    form.workers.choices = [(w.id, w.full_name) for w in _active_executor_workers_query().all()]
    if form.validate_on_submit():
        try:
            raw_cid = form.client_id.data
            client_id = int(raw_cid) if raw_cid not in (None, 0) else None
            if client_id is None:
                if not form.full_name.data or not form.address.data:
                    flash("Укажите клиента или ФИО и адрес.", "danger")
                    return render_template("requests/add.html", form=form)
                # Создание нового клиента
                new_client = Client(
                    full_name=form.full_name.data, address=form.address.data, phone=form.phone.data
                )
                db.session.add(new_client)
                db.session.commit()
                client_id = new_client.id
            type_map = {"emergency": "аварийная", "repair": "ремонтная", "planned": "плановая"}
            req_type = type_map.get(form.type.data, "") if form.type.data else None
            new_status = "assigned"
            req = Request(
                client_id=client_id,
                contract_id=form.contract_id.data if form.contract_id.data != 0 else None,
                equipment_id=form.equipment_id.data if form.equipment_id.data != 0 else None,
                full_name=form.full_name.data,
                address=form.address.data,
                phone=form.phone.data,
                description=form.description.data,
                type=req_type,
                visit_type=_visit_type_from_choice(form.visit_type.data),
                service_type=form.service_type.data,
                warranty_reason=form.warranty_reason.data,
                urgent_price=form.urgent_price.data,
                contract_regulated_price=form.contract_regulated_price.data,
                materials_cost=form.materials_cost.data,
                total_price=form.total_price.data,
                estimated_time=form.estimated_time.data,
                planned_date=form.planned_date.data,
                planned_start_time=form.planned_start_time.data,
                planned_end_time=form.planned_end_time.data,
                status=new_status,
                mode=form.mode.data or "normal",
                created_by_user_id=current_user.id,
            )
            req.checklist_template_id = _resolve_checklist_template_id_for_request(
                req.equipment_id, req.type
            )
            db.session.add(req)
            db.session.commit()
            req.request_number = f"REQ-{req.id:06d}"
            for worker_id in form.workers.data or []:
                worker = _active_executor_workers_query().filter(Worker.id == worker_id).first()
                if worker:
                    req.workers.append(worker)
            db.session.commit()
            flash("Заявка добавлена.", "success")
            return redirect(url_for("requests.list_requests"))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f"Ошибка: {str(e)}", "danger")
    return render_template("requests/add.html", form=form)


@requests_bp.route("/view/<int:id>", methods=["GET"])
@login_required
def view_request(id):
    req = Request.query.options(
        joinedload(Request.workers),
        joinedload(Request.action_logs),
    ).get_or_404(id)
    if not _request_visible_to_user(req):
        flash("Доступ только к своим заявкам или заявкам без назначения.", "danger")
        return redirect(url_for("requests.list_requests"))
    from_calendar = request.args.get("from") == "calendar"
    default_back = (
        url_for("requests.calendar") if from_calendar else url_for("requests.list_requests")
    )
    back_url = _safe_next_url(default_back)
    timeline = _build_request_timeline(req)
    return render_template(
        "requests/view.html",
        req=req,
        from_calendar=from_calendar,
        back_url=back_url,
        timeline=timeline,
    )


@requests_bp.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_request(id):
    if current_user.role != "admin":
        flash("Доступ только для админа.", "danger")
        return redirect(url_for("requests.list_requests"))
    req = Request.query.get_or_404(id)
    next_url = _safe_next_url(url_for("requests.view_request", id=req.id))
    form = RequestForm(obj=req)
    type_reverse = {
        "аварийная": "emergency",
        "emergency": "emergency",
        "ремонтная": "repair",
        "repair": "repair",
        "плановая": "planned",
        "planned": "planned",
    }
    form.type.data = type_reverse.get(req.type, "planned") if req.type else "planned"
    form.visit_type.data = req.visit_type.value if req.visit_type else "repair"
    form.contract_id.choices = [(0, "Нет")] + [
        (c.id, c.contract_type) for c in Contract.query.all()
    ]
    form.equipment_id.choices = [(0, "Нет")] + [(e.id, e.model) for e in Equipment.query.all()]
    _seen = set()
    _wchoices = []
    for w in Worker.query.filter(Worker.is_active.is_(True)).order_by(Worker.full_name).all():
        _wchoices.append((w.id, w.full_name))
        _seen.add(w.id)
    for w in req.workers:
        if w.id not in _seen:
            _wchoices.append((w.id, f"{w.full_name} (уволен)"))
            _seen.add(w.id)
    form.workers.choices = _wchoices
    form.workers.data = [w.id for w in req.workers]
    _manual_status = [
        ("assigned", "Назначена"),
        ("closed", "Закрыта"),
        ("cancelled", "Отменена"),
    ]
    if req.status == RequestStatus.overdue:
        form.status.choices = [("", "—")] + _manual_status
        form.status.data = ""
    else:
        form.status.choices = list(_manual_status)
        if req.status is not None:
            form.status.data = req.status.value
    if req.mode is not None:
        form.mode.data = req.mode.value
    picker_label = ""
    if req.client:
        addr = (req.client.address or "")[:60]
        picker_label = f"{req.client.full_name or '—'} · {req.client.phone or '—'} · {addr}"
    if form.validate_on_submit():
        try:
            raw_cid = form.client_id.data
            client_id = int(raw_cid) if raw_cid not in (None, 0) else None
            if client_id is None:
                if not form.full_name.data or not form.address.data:
                    flash("Укажите клиента или ФИО и адрес.", "danger")
                    return render_template(
                        "requests/edit.html",
                        form=form,
                        req=req,
                        client_picker_label=picker_label,
                        next_url=next_url,
                    )
                # Создание нового клиента, если не выбран существующий
                new_client = Client(
                    full_name=form.full_name.data, address=form.address.data, phone=form.phone.data
                )
                db.session.add(new_client)
                db.session.commit()
                client_id = new_client.id
            req.client_id = client_id
            selected_client = Client.query.get(client_id) if client_id else None
            req.contract_id = form.contract_id.data if form.contract_id.data != 0 else None
            req.equipment_id = form.equipment_id.data if form.equipment_id.data != 0 else None
            req.full_name = form.full_name.data
            req.address = selected_client.address if selected_client else form.address.data
            req.phone = selected_client.phone if selected_client else form.phone.data
            req.description = form.description.data
            req.type = (
                {"emergency": "аварийная", "repair": "ремонтная", "planned": "плановая"}.get(
                    form.type.data, ""
                )
                if form.type.data
                else None
            )
            req.visit_type = _visit_type_from_choice(form.visit_type.data)
            req.service_type = form.service_type.data
            req.warranty_reason = form.warranty_reason.data
            req.materials_cost = form.materials_cost.data
            req.total_price = form.total_price.data
            req.planned_date = form.planned_date.data
            req.planned_start_time = form.planned_start_time.data
            req.planned_end_time = form.planned_end_time.data
            if form.status.data:
                try:
                    new_s = RequestStatus(form.status.data)
                    if new_s in (
                        RequestStatus.assigned,
                        RequestStatus.closed,
                        RequestStatus.cancelled,
                    ):
                        req.status = new_s
                except ValueError:
                    pass
            if form.mode.data:
                try:
                    req.mode = RequestMode(form.mode.data)
                except ValueError:
                    pass
            req.checklist_template_id = _resolve_checklist_template_id_for_request(
                req.equipment_id, req.type
            )
            req.updated_by_user_id = current_user.id
            req.updated_at = datetime.utcnow()
            req.workers = []
            for worker_id in form.workers.data or []:
                wk = Worker.query.get(worker_id)
                if wk:
                    req.workers.append(wk)
            db.session.commit()
            flash("Заявка обновлена.", "success")
            return redirect(next_url)
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f"Ошибка: {str(e)}", "danger")
    return render_template(
        "requests/edit.html",
        form=form,
        req=req,
        client_picker_label=picker_label,
        next_url=next_url,
    )


@requests_bp.route("/create_work_order/<int:id>", methods=["GET", "POST"])
@login_required
def create_work_order(id):
    if current_user.role != "admin":
        flash("Доступ только для админа.", "danger")
        return redirect(url_for("requests.list_requests"))
    req = Request.query.get_or_404(id)
    # Логика создания наряда (work order)
    # Пока просто создание пустого наряда
    work_order = WorkOrder(
        request_id=req.id,
        description="Наряд для заявки #" + req.request_number,
        created_at=datetime.utcnow(),
    )
    db.session.add(work_order)
    db.session.commit()
    flash("Наряд создан.", "success")
    return redirect(url_for("requests.view_request", id=id))


@requests_bp.route("/assign/<int:id>", methods=["POST"])
@login_required
def assign_request(id):
    req = Request.query.get_or_404(id)
    worker = None
    if getattr(current_user, "worker_id", None):
        worker = (
            _active_executor_workers_query().filter(Worker.id == current_user.worker_id).first()
        )
    if worker is None:
        worker = _active_executor_workers_query().filter(Worker.id == current_user.id).first()
    if worker and worker not in req.workers:
        req.workers.append(worker)
        db.session.commit()
        flash("Заявка присвоена.", "success")
    return redirect(url_for("requests.list_requests"))


@requests_bp.route("/assign_worker", methods=["POST"])
@login_required
def assign_worker():
    if current_user.role != "admin":
        flash("Доступ только для админа.", "danger")
        return redirect(url_for("requests.today_requests"))
    worker_id = request.form.get("worker_id")
    request_ids = request.form.getlist("request_ids")
    try:
        worker_id_int = int(worker_id) if worker_id else None
    except (TypeError, ValueError):
        worker_id_int = None
    worker = (
        _active_executor_workers_query().filter(Worker.id == worker_id_int).first()
        if worker_id_int
        else None
    )
    if not worker:
        flash("Мастер не найден.", "danger")
        return redirect(url_for("requests.today_requests"))
    for req_id in request_ids:
        req = Request.query.get(req_id)
        if req and worker not in req.workers:
            req.workers.append(worker)
    db.session.commit()
    flash("Мастер назначен.", "success")
    return redirect(url_for("requests.today_requests"))


@requests_bp.route("/close/<int:id>", methods=["POST"])
@login_required
def close_request(id):
    req = Request.query.get_or_404(id)
    if current_user.role not in ["engineer", "master"]:
        flash("Доступ только для мастера.", "danger")
        return redirect(url_for("requests.list_requests"))
    if req.workers and not any(w.id == current_user.id for w in req.workers):
        flash("Заявка назначена другому исполнителю.", "danger")
        return redirect(url_for("requests.list_requests"))
    # Закомментировано: чек-лист процедура
    # form = ChecklistForm()
    # if form.validate_on_submit():
    #     # Сохранить чек-лист (галочки/комментарий) в JSON или таблицу
    #     req.status = 'closed'
    #     req.actual_end_time = datetime.utcnow()
    #     db.session.commit()
    #     flash('Заявка закрыта после чек-листа.', 'success')
    # else:
    #     return render_template('requests/close.html', form=form, req=req)
    # Пока просто закрытие
    req.status = "closed"
    db.session.commit()
    flash("Заявка закрыта (чек-лист закомментирован).", "success")
    return redirect(url_for("requests.list_requests"))


@requests_bp.route("/cancel/<int:id>", methods=["POST"])
@login_required
def cancel_request(id):
    if current_user.role != "admin":
        flash("Доступ только для админа.", "danger")
        return redirect(url_for("requests.list_requests"))
    req = Request.query.get_or_404(id)
    if req.status == RequestStatus.closed:
        flash("Закрытую заявку нельзя отменить.", "warning")
        return redirect(url_for("requests.view_request", id=id))
    if req.status == RequestStatus.cancelled:
        flash("Заявка уже отменена.", "info")
        return redirect(url_for("requests.view_request", id=id))

    old_status = req.status.value if req.status else None
    cancel_reason = (request.form.get("cancel_reason") or "").strip()
    if cancel_reason:
        suffix = f"\n[ОТМЕНЕНО] {cancel_reason}"
        req.comment = (req.comment or "") + suffix
    req.status = RequestStatus.cancelled
    req.updated_by_user_id = current_user.id
    req.updated_at = datetime.utcnow()
    db.session.add(
        RequestActionLog(
            request_id=req.id,
            user_id=current_user.id,
            action="cancel",
            old_status=old_status,
            new_status=RequestStatus.cancelled.value,
            old_mode=req.mode.value if req.mode else None,
            new_mode=req.mode.value if req.mode else None,
            extra={"reason": cancel_reason} if cancel_reason else None,
        )
    )
    db.session.commit()
    flash("Заявка отменена и сохранена в истории.", "success")
    return redirect(url_for("requests.view_request", id=id))


@requests_bp.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_request(id):
    if current_user.role != "admin":
        flash("Доступ только для админа.", "danger")
        return redirect(url_for("requests.list_requests"))
    req = Request.query.get_or_404(id)
    if req.contract_scope_uid:
        flash(
            "Эта заявка связана со строкой перечня договора и не удаляется вручную. Удалите/измените строку в перечне договора.",
            "warning",
        )
        return redirect(url_for("requests.view_request", id=req.id))
    try:
        # Отвязываем медиа, чтобы не потерять фото/файлы
        Media.query.filter_by(request_id=req.id).update({Media.request_id: None})
        db.session.delete(req)
        db.session.commit()
        flash("Заявка удалена. Связанные медиа сохранены.", "success")
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f"Ошибка при удалении заявки: {str(e)}", "danger")
    return redirect(url_for("requests.list_requests"))


@requests_bp.route("/calendar")
@login_required
def calendar():
    if current_user.role == "admin":
        url = url_for("schedule.index")
        if request.query_string:
            url = url + "?" + request.query_string.decode()
        return redirect(url)
    clients = Client.query.all()
    workers = _active_executor_workers_query().all()
    statuses = [s.value for s in RequestStatus]
    cid = request.args.get("client_id", "all")
    calendar_client_label = ""
    if cid and cid != "all":
        try:
            oc = Client.query.get(int(cid))
            if oc:
                calendar_client_label = f"{oc.full_name or '—'} · {oc.phone or '—'}"
        except (ValueError, TypeError):
            pass
    template = "requests/calendar_mobile.html"
    return render_template(
        template,
        clients=clients,
        workers=workers,
        statuses=statuses,
        calendar_client_id=cid,
        calendar_client_label=calendar_client_label,
    )


@requests_bp.route("/api/request/<int:id>/summary")
@login_required
def api_request_summary(id):
    """Краткие данные заявки для модального окна план-графика."""
    req = Request.query.get_or_404(id)
    if not _request_visible_to_user(req):
        return jsonify({"error": "forbidden"}), 403

    client_name = req.client.full_name if req.client else (req.full_name or "—")
    address = req.client.address if req.client else (req.address or "—")
    phone = req.client.phone if req.client else (req.phone or "—")
    workers_str = ", ".join(w.full_name for w in req.workers) or "—"
    req_type = req.type or (req.service_type.value if req.service_type else "")
    status_val = req.status.value if req.status else "—"

    def _fmt_dt(dt):
        if not dt:
            return None
        if isinstance(dt, datetime):
            return dt.strftime("%d.%m.%Y %H:%M")
        return str(dt)

    if req.visit_type == VisitType.survey:
        visit_label = "Обследование"
    else:
        visit_label = "Ремонтный выезд"

    return jsonify(
        {
            "id": req.id,
            "request_number": req.request_number or str(req.id),
            "title": (req.description or "Заявка")[:200],
            "description": req.description or "—",
            "client_name": client_name,
            "address": address,
            "phone": phone,
            "workers": workers_str,
            "planned_date": req.planned_date.strftime("%d.%m.%Y") if req.planned_date else "—",
            "planned_start": _fmt_dt(req.planned_start_time),
            "planned_end": _fmt_dt(req.planned_end_time),
            "status": status_val,
            "type": req_type,
            "visit_type": req.visit_type.value if req.visit_type else None,
            "visit_type_label": visit_label,
            "comment": req.comment or "",
            "can_edit": current_user.role == "admin",
            "view_url": url_for("requests.view_request", id=req.id) + "?from=calendar",
            "edit_url": url_for("requests.edit_request", id=req.id),
        }
    )


@requests_bp.route("/api/events")
@login_required
def api_events():
    events = []
    for req in Request.query.all():
        start, end = planned_range_for_request(req)
        if not start:
            continue
        title = req.description or "Заявка"
        if req.client_id and req.client:
            title += f" для {req.client.full_name}"
        elif req.full_name:
            title += f" для {req.full_name}"
        workers_names = ", ".join([w.full_name for w in req.workers])
        if workers_names:
            title += f" ({workers_names})"
        req_type = req.type or (req.service_type.value if req.service_type else "")
        if req.status and req.status.value == "overdue":
            color = "#dc3545"
        elif (
            req.planned_date
            and req.planned_date < date.today()
            and req.status
            not in (RequestStatus.closed, RequestStatus.cancelled, RequestStatus.overdue)
        ):
            color = "#dc3545"
        elif req.status and req.status.value == "closed":
            color = "#198754"
        elif req.status and req.status.value == "cancelled":
            color = "#adb5bd"
        elif req_type in ["аварийная", "emergency"]:
            color = "#dc3545"
        elif req_type in ["ремонтная", "repair"]:
            color = "#fd7e14"
        elif req_type in ["плановая", "planned"]:
            color = "#198754"
        elif req.status and req.status.value == "assigned":
            color = "#0d6efd"
        else:
            color = "#6c757d"
        events.append(
            {
                "id": req.id,
                "title": title,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "allDay": False,
                "color": color,
                "backgroundColor": color,
                "borderColor": color,
                "textColor": "#ffffff",
                "extendedProps": {"layer": "request"},
            }
        )
    if current_user.role in ["engineer", "master"]:
        filtered = []
        for e in events:
            req = Request.query.get(e["id"])
            if req and _request_visible_to_user(req):
                filtered.append(e)
        events = filtered
    return jsonify(events)


@requests_bp.route("/api/shift-backgrounds")
@login_required
def api_shift_backgrounds():
    """Слой смен из БД (worker_shifts); заявки рисуются поверх. show=0 — отключить."""
    if request.args.get("show") == "0":
        return jsonify([])
    start_s = request.args.get("start")
    end_s = request.args.get("end")
    if not start_s or not end_s:
        return jsonify([])
    try:
        start_dt = parse_fc_iso(start_s)
        end_dt = parse_fc_iso(end_s)
        q = (
            WorkerShift.query.options(joinedload(WorkerShift.worker))
            .join(Worker)
            .join(Users, Users.worker_id == Worker.id)
            .filter(
                WorkerShift.shift_date >= start_dt.date(),
                WorkerShift.shift_date < end_dt.date(),
                Worker.is_active.is_(True),
                Users.role.in_(EXECUTOR_ROLES),
            )
        )
        wid = request.args.get("worker_id", type=int)
        if wid:
            q = q.filter(WorkerShift.worker_id == wid)
        shifts = q.all()
        return jsonify(shift_layer_events_from_db(shifts))
    except (ValueError, TypeError):
        return jsonify([])


def _parse_fullcalendar_iso(s: str) -> datetime:
    return parse_fc_iso(s)


@requests_bp.route("/api/update_event", methods=["POST"])
@login_required
def api_update_event():
    if current_user.role != "admin":
        return jsonify({"success": False, "error": "Доступ только для админа"})
    data = request.json
    req = Request.query.get_or_404(data["id"])
    if req.status in (RequestStatus.closed, RequestStatus.cancelled):
        return jsonify(
            {"success": False, "error": "Нельзя переносить закрытую или отменённую заявку"}
        )
    start = _parse_fullcalendar_iso(data["start"])
    prev_dur = None
    if req.planned_start_time and req.planned_end_time:
        prev_dur = req.planned_end_time - req.planned_start_time
    req.planned_date = start.date()
    req.planned_start_time = start
    if prev_dur:
        req.planned_end_time = start + prev_dur
    else:
        req.planned_end_time = start + timedelta(hours=2)
    db.session.commit()
    return jsonify({"success": True})
