from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.services.request_analytics import calculate_master_time_analytics

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/masters", methods=["GET"])
@login_required
def masters():
    if current_user.role != "admin":
        flash("Доступ только для админа.", "danger")
        return redirect(url_for("requests.list_requests"))

    today = date.today()
    date_from_raw = (request.args.get("date_from") or "").strip()
    date_to_raw = (request.args.get("date_to") or "").strip()

    if date_from_raw:
        try:
            date_from = datetime.strptime(date_from_raw, "%Y-%m-%d").date()
        except ValueError:
            date_from = today.replace(day=1)
            date_from_raw = date_from.isoformat()
    else:
        date_from = today.replace(day=1)
        date_from_raw = date_from.isoformat()

    if date_to_raw:
        try:
            date_to = datetime.strptime(date_to_raw, "%Y-%m-%d").date()
        except ValueError:
            date_to = today
            date_to_raw = date_to.isoformat()
    else:
        date_to = today
        date_to_raw = date_to.isoformat()

    if date_from > date_to:
        date_from, date_to = date_to, date_from
        date_from_raw = date_from.isoformat()
        date_to_raw = date_to.isoformat()

    rows, totals = calculate_master_time_analytics(date_from, date_to)
    return render_template(
        "analytics/masters.html",
        rows=rows,
        totals=totals,
        date_from=date_from_raw,
        date_to=date_to_raw,
    )
