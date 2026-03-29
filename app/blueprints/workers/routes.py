# Path: app/blueprints/workers/routes.py
from datetime import datetime, time, timedelta
from urllib.parse import urlparse

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.all_models import Users, Worker, WorkerShift
from app.utils.request_calendar import (
    parse_fc_iso,
    shift_layer_events_from_db,
)

workers_bp = Blueprint("workers", __name__)
EXECUTOR_ROLES = ("master", "engineer")


def _safe_next_url(default_url):
    raw = (request.args.get("next") if request.method == "GET" else request.form.get("next")) or ""
    raw = raw.strip()
    if raw and raw.startswith("/"):
        parsed = urlparse(raw)
        if not parsed.scheme and not parsed.netloc:
            return raw
    return default_url


def _normalize_username(raw: str) -> str:
    return (raw or "").strip()


def _active_executor_workers_query():
    return (
        Worker.query.join(Users, Users.worker_id == Worker.id)
        .filter(
            Worker.is_active.is_(True),
            Users.role.in_(EXECUTOR_ROLES),
        )
        .order_by(Worker.full_name)
    )


@workers_bp.route("/", methods=["GET"])
@login_required
def index():
    return redirect(url_for("admin.index"))


@workers_bp.route("/list", methods=["GET"])
@login_required
def list_workers():
    return redirect(url_for("admin.index"))


@workers_bp.route("/calendar", methods=["GET"])
@login_required
def worker_calendar():
    if current_user.role != "admin":
        flash("Календарь исполнителей доступен только администратору.", "danger")
        return redirect(url_for("requests.list_requests"))
    workers = _active_executor_workers_query().all()
    return render_template("workers/calendar.html", workers=workers)


@workers_bp.route("/shifts/bulk", methods=["POST"])
@login_required
def bulk_shifts():
    """Массовое создание/обновление смен по датам (один исполнитель, диапазон дней)."""
    if current_user.role != "admin":
        flash("Доступ только администратору.", "danger")
        return redirect(url_for("requests.list_requests"))
    worker_id = request.form.get("worker_id", type=int)
    date_from_s = (request.form.get("date_from") or "").strip()
    date_to_s = (request.form.get("date_to") or "").strip()
    if not worker_id or not date_from_s or not date_to_s:
        flash("Укажите исполнителя и обе даты.", "danger")
        return redirect(url_for("workers.worker_calendar"))
    worker = _active_executor_workers_query().filter(Worker.id == worker_id).first()
    if not worker:
        flash("Исполнитель не найден.", "danger")
        return redirect(url_for("workers.worker_calendar"))

    def _parse_t(name, h, m):
        raw = (request.form.get(name) or "").strip()
        if not raw:
            return time(h, m)
        parts = raw.replace(".", ":").split(":")
        try:
            return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        except (ValueError, IndexError):
            return time(h, m)

    t0 = _parse_t("time_start", 9, 0)
    t1 = _parse_t("time_end", 19, 0)
    try:
        df = datetime.strptime(date_from_s, "%Y-%m-%d").date()
        dt = datetime.strptime(date_to_s, "%Y-%m-%d").date()
    except ValueError:
        flash("Неверный формат даты.", "danger")
        return redirect(url_for("workers.worker_calendar"))
    if dt < df:
        df, dt = dt, df

    now = datetime.utcnow()
    d = df
    while d <= dt:
        stmt = (
            insert(WorkerShift)
            .values(
                worker_id=worker_id,
                shift_date=d,
                time_start=t0,
                time_end=t1,
                created_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_worker_shift_day",
                set_={"time_start": t0, "time_end": t1},
            )
        )
        db.session.execute(stmt)
        d += timedelta(days=1)
    db.session.commit()
    flash(f"Смены сохранены для {worker.full_name}: {df} — {dt}.", "success")
    return redirect(url_for("workers.worker_calendar", worker_id=worker_id))


def _parse_time_body(val, default_h, default_m):
    if not val:
        return time(default_h, default_m)
    if isinstance(val, str):
        parts = val.replace(".", ":").strip().split(":")
        try:
            return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        except (ValueError, IndexError):
            return time(default_h, default_m)
    return time(default_h, default_m)


@workers_bp.route("/shifts/add-days", methods=["POST"])
@login_required
def shifts_add_days():
    """Добавить/обновить смены выбранного мастера на указанные дни (9:00–19:00 по умолчанию)."""
    if current_user.role != "admin":
        return jsonify({"ok": False, "error": "forbidden"}), 403
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    try:
        worker_id = int(worker_id) if worker_id is not None else None
    except (TypeError, ValueError):
        worker_id = None
    dates = data.get("dates") or []
    if not worker_id or not dates:
        return jsonify({"ok": False, "error": "Нужны worker_id и dates"}), 400
    worker = _active_executor_workers_query().filter(Worker.id == worker_id).first()
    if not worker:
        return jsonify({"ok": False, "error": "Исполнитель не найден"}), 404
    t0 = _parse_time_body(data.get("time_start"), 9, 0)
    t1 = _parse_time_body(data.get("time_end"), 19, 0)
    upserted = 0
    seen = set()
    now = datetime.utcnow()
    for raw in dates:
        s = (raw or "")[:10]
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d in seen:
            continue
        seen.add(d)
        stmt = (
            insert(WorkerShift)
            .values(
                worker_id=worker_id,
                shift_date=d,
                time_start=t0,
                time_end=t1,
                created_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_worker_shift_day",
                set_={"time_start": t0, "time_end": t1},
            )
        )
        db.session.execute(stmt)
        upserted += 1
    db.session.commit()
    return jsonify({"ok": True, "upserted": upserted})


@workers_bp.route("/shifts/delete-days", methods=["POST"])
@login_required
def shifts_delete_days():
    """Удалить все смены всех исполнителей на указанные календарные дни."""
    if current_user.role != "admin":
        return jsonify({"ok": False, "error": "forbidden"}), 403
    data = request.get_json(silent=True) or {}
    dates = data.get("dates") or []
    if not dates:
        return jsonify({"ok": False, "error": "Нужен список dates"}), 400
    ds = []
    seen = set()
    for raw in dates:
        s = (raw or "")[:10]
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d not in seen:
            seen.add(d)
            ds.append(d)
    if not ds:
        return jsonify({"ok": False, "error": "Нет валидных дат"}), 400
    deleted = WorkerShift.query.filter(WorkerShift.shift_date.in_(ds)).delete(
        synchronize_session=False
    )
    db.session.commit()
    return jsonify({"ok": True, "deleted": deleted})


@workers_bp.route("/api/events")
@login_required
def api_worker_events():
    """Слой смен из БД (без заявок — только календарь людей)."""
    if current_user.role != "admin":
        return jsonify({"error": "forbidden"}), 403

    worker_filter = request.args.get("worker_id", type=int)
    events = []

    start_s = request.args.get("start")
    end_s = request.args.get("end")
    if start_s and end_s:
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
            if worker_filter:
                q = q.filter(WorkerShift.worker_id == worker_filter)
            events.extend(shift_layer_events_from_db(q.all()))
        except (ValueError, TypeError):
            pass

    return jsonify(events)


@workers_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_worker():
    if current_user.role != "admin":
        flash("Доступ запрещен.", "danger")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role")
        username = _normalize_username(request.form.get("username", ""))
        password = request.form.get("password", "") or ""
        account_role = (request.form.get("account_role") or role or "").strip()
        if not full_name or not role or not username or not password:
            flash("Заполните обязательные поля (ФИО, роль, логин и пароль).", "danger")
            return redirect(url_for("workers.create_worker"))
        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            flash("Пользователь с таким логином уже существует.", "danger")
            return redirect(url_for("workers.create_worker"))
        new_worker = Worker(
            full_name=full_name,
            phone=phone or None,
            role=role,
            is_active=True,
        )
        db.session.add(new_worker)
        db.session.flush()
        new_user = Users(
            username=username,
            password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
            role=account_role or role,
            worker_id=new_worker.id,
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Исполнитель и учетная запись созданы.", "success")
        return redirect(url_for("admin.index"))
    return render_template("workers/workers_create.html")


@workers_bp.route("/edit/<int:worker_id>", methods=["GET", "POST"])
@login_required
def edit_worker(worker_id):
    if current_user.role != "admin":
        flash("Доступ запрещен.", "danger")
        return redirect(url_for("auth.login"))
    worker = Worker.query.get_or_404(worker_id)
    linked_user = worker.linked_user
    next_url = _safe_next_url(url_for("admin.index"))
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role")
        username = _normalize_username(request.form.get("username", ""))
        account_role = (request.form.get("account_role") or role or "").strip()
        password = request.form.get("password", "") or ""
        if not full_name or not role:
            flash("Заполните обязательные поля (ФИО и роль).", "danger")
            return redirect(url_for("workers.edit_worker", worker_id=worker.id, next=next_url))
        worker.full_name = full_name
        worker.phone = phone or None
        worker.role = role
        color_raw = (request.form.get("color") or "").strip()
        if color_raw.startswith("#") and len(color_raw) >= 4:
            worker.color = color_raw[:16]
        else:
            worker.color = None
        if username:
            existing_other = Users.query.filter(
                Users.username == username,
                Users.id != (linked_user.id if linked_user else 0),
            ).first()
            if existing_other:
                flash("Пользователь с таким логином уже существует.", "danger")
                return redirect(url_for("workers.edit_worker", worker_id=worker.id, next=next_url))
            if linked_user:
                linked_user.username = username
                linked_user.role = account_role or role
                if password:
                    linked_user.password_hash = generate_password_hash(
                        password, method="pbkdf2:sha256"
                    )
            else:
                if not password:
                    flash("Для новой учетной записи исполнителя укажите пароль.", "danger")
                    return redirect(
                        url_for("workers.edit_worker", worker_id=worker.id, next=next_url)
                    )
                linked_user = Users(
                    username=username,
                    password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
                    role=account_role or role,
                    worker_id=worker.id,
                )
                db.session.add(linked_user)
        elif linked_user:
            linked_user.role = account_role or role
            if password:
                linked_user.password_hash = generate_password_hash(password, method="pbkdf2:sha256")
        db.session.commit()
        flash("Исполнитель и учетная запись обновлены.", "success")
        return redirect(next_url)
    return render_template(
        "workers/workers_edit.html", worker=worker, linked_user=linked_user, next_url=next_url
    )


@workers_bp.route("/delete/<int:worker_id>", methods=["POST"])
@login_required
def delete_worker(worker_id):
    if current_user.role != "admin":
        flash("Доступ запрещен.", "danger")
        return redirect(url_for("auth.login"))
    worker = Worker.query.get_or_404(worker_id)
    if not getattr(worker, "is_active", True):
        flash("Исполнитель уже отмечен как уволенный.", "info")
        return redirect(url_for("admin.index"))
    worker.is_active = False
    worker.inactive_at = datetime.utcnow()
    db.session.commit()
    flash("Исполнитель уволен: запись сохранена в истории заявок и календаре.", "success")
    return redirect(url_for("admin.index"))
