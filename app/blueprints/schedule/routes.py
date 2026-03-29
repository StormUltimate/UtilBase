"""Маршруты план-графика: страница, JSON, назначение, экспорт."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime

from flask import Response, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.schedule.defaults import schedule_defaults
from app.blueprints.schedule.service import (
    _parse_date,
    active_executor_workers,
    build_timeline_payload,
    distinct_equipment_types,
    fetch_requests_for_period,
    period_bounds,
)
from app.extensions import db
from app.models.all_models import Request, RequestStatus, Worker

from . import schedule_bp

REQUEST_STATUS_VALUES = [e.value for e in RequestStatus]


def _admin_only():
    return current_user.is_authenticated and current_user.role == "admin"


def _parse_multi_str(name: str) -> list[str]:
    vals = request.args.getlist(name)
    if vals:
        return [v.strip() for v in vals if v and v.strip()]
    raw = (request.args.get(name) or "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _parse_multi_int(name: str) -> list[int]:
    out: list[int] = []
    for s in _parse_multi_str(name):
        try:
            out.append(int(s))
        except ValueError:
            continue
    return out


def _filters_from_request():
    return {
        "q": (request.args.get("q") or "").strip() or None,
        "worker_ids": _parse_multi_int("workers") or None,
        "statuses": _parse_multi_str("statuses") or None,
        "equipment_types": _parse_multi_str("eq_types") or None,
        "maintenance_only": request.args.get("maintenance_only") in ("1", "true", "yes", "on"),
    }


@schedule_bp.route("/")
@login_required
def index():
    if not _admin_only():
        return redirect(url_for("requests.calendar"))
    anchor = _parse_date(request.args.get("date")) or date.today()
    view = (request.args.get("view") or "week").lower()
    if view not in ("day", "week", "month"):
        view = "week"
    start_d, end_d = period_bounds(anchor, view)
    cfg = schedule_defaults(current_app)
    workers = active_executor_workers().all()
    statuses = REQUEST_STATUS_VALUES
    eq_types = distinct_equipment_types()
    return render_template(
        "schedule/index.html",
        schedule_config=cfg,
        anchor_date=anchor.isoformat(),
        view_mode=view,
        period_start=start_d.isoformat(),
        period_end=end_d.isoformat(),
        workers=workers,
        statuses=statuses,
        equipment_types=eq_types,
        shifts_manage_url=url_for("workers.worker_calendar"),
    )


@schedule_bp.route("/data")
@login_required
def api_data():
    if not _admin_only():
        return jsonify({"error": "forbidden"}), 403
    anchor = _parse_date(request.args.get("date")) or date.today()
    view = (request.args.get("view") or "week").lower()
    if view not in ("day", "week", "month"):
        view = "week"
    start_d, end_d = period_bounds(anchor, view)
    filters = _filters_from_request()
    day_u = anchor if view == "day" else date.today()
    if start_d <= date.today() <= end_d:
        day_u = date.today()
    elif anchor <= end_d and anchor >= start_d:
        day_u = anchor

    payload = build_timeline_payload(
        start_d=start_d,
        end_d=end_d,
        view=view,
        day_for_unassigned=day_u,
        filters=filters,
    )
    payload["meta"] = {"config": schedule_defaults(current_app)}
    return jsonify(payload)


@schedule_bp.route("/assign", methods=["POST"])
@login_required
def api_assign():
    if not _admin_only():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    data = request.get_json(silent=True) or {}
    rid = data.get("request_id")
    worker_ids = data.get("worker_ids")
    if not rid or not isinstance(worker_ids, list):
        return jsonify({"ok": False, "error": "bad_request"}), 400
    req = Request.query.get_or_404(int(rid))
    new_workers = []
    for wid in worker_ids:
        try:
            w = Worker.query.get(int(wid))
        except (TypeError, ValueError):
            continue
        if w and w.is_active:
            new_workers.append(w)
    req.workers = new_workers
    ps = data.get("planned_start")
    pe = data.get("planned_end")
    if ps:
        try:
            req.planned_start_time = datetime.fromisoformat(str(ps).replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        except ValueError:
            pass
    if pe:
        try:
            req.planned_end_time = datetime.fromisoformat(str(pe).replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        except ValueError:
            pass
    if req.planned_start_time and not req.planned_date:
        req.planned_date = req.planned_start_time.date()
    elif req.planned_start_time and req.planned_date != req.planned_start_time.date():
        req.planned_date = req.planned_start_time.date()
    db.session.commit()
    return jsonify({"ok": True})


@schedule_bp.route("/export.csv")
@login_required
def export_csv():
    if not _admin_only():
        return redirect(url_for("auth.login"))
    anchor = _parse_date(request.args.get("date")) or date.today()
    view = (request.args.get("view") or "week").lower()
    if view not in ("day", "week", "month"):
        view = "week"
    start_d, end_d = period_bounds(anchor, view)
    filters = _filters_from_request()
    rows = fetch_requests_for_period(
        start_d,
        end_d,
        q_search=filters.get("q"),
        worker_ids=filters.get("worker_ids"),
        statuses=filters.get("statuses"),
        equipment_types=filters.get("equipment_types"),
        maintenance_only=bool(filters.get("maintenance_only")),
    )

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        ["id", "number", "planned_date", "start", "end", "client", "status", "from_contract_scope"]
    )
    for req in rows:
        client_name = req.client.full_name if req.client else (req.full_name or "")
        ps = req.planned_start_time.isoformat() if req.planned_start_time else ""
        pe = req.planned_end_time.isoformat() if req.planned_end_time else ""
        w.writerow(
            [
                req.id,
                req.request_number or "",
                req.planned_date.isoformat() if req.planned_date else "",
                ps,
                pe,
                client_name,
                req.status.value if req.status else "",
                "yes" if req.contract_scope_uid else "no",
            ]
        )
    return Response(
        buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=schedule-{start_d}_{end_d}.csv"},
    )
