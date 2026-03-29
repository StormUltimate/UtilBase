from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time

from sqlalchemy.orm import joinedload

from app.models.all_models import Request, RequestActionLog


def format_minutes(total_minutes: int) -> str:
    minutes = max(0, int(total_minutes or 0))
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} ч {mins} мин"
    if hours:
        return f"{hours} ч"
    return f"{mins} мин"


def calculate_master_time_analytics(date_from: date, date_to: date):
    start_dt = datetime.combine(date_from, time.min)
    end_dt = datetime.combine(date_to, time.max)

    logs = (
        RequestActionLog.query.options(
            joinedload(RequestActionLog.user),
            joinedload(RequestActionLog.request).joinedload(Request.workers),
        )
        .filter(
            RequestActionLog.action == "mode_change",
            RequestActionLog.created_at >= start_dt,
            RequestActionLog.created_at <= end_dt,
            RequestActionLog.new_mode.in_(["on_way", "arrived", "in_progress", "completed"]),
        )
        .order_by(RequestActionLog.request_id.asc(), RequestActionLog.created_at.asc())
        .all()
    )

    by_request_actor = defaultdict(list)
    for log in logs:
        actor_id = log.user_id or 0
        by_request_actor[(log.request_id, actor_id)].append(log)

    rows_by_worker = {}
    for (_request_id, _actor_id), worker_logs in by_request_actor.items():
        req = worker_logs[0].request if worker_logs else None
        if not req:
            continue

        actor = worker_logs[0].user if worker_logs else None
        if actor and getattr(actor, "linked_worker", None):
            worker_name = actor.linked_worker.full_name
        elif actor and getattr(actor, "username", None):
            worker_name = actor.username
        elif req.workers:
            worker_name = req.workers[0].full_name
        else:
            worker_name = "Неизвестный мастер"

        first_mode_at = {}
        for log in worker_logs:
            first_mode_at.setdefault(log.new_mode, log.created_at)

        on_way_at = first_mode_at.get("on_way")
        arrived_at = first_mode_at.get("arrived")
        in_progress_at = first_mode_at.get("in_progress") or req.actual_start_time
        completed_at = first_mode_at.get("completed") or req.actual_end_time

        travel_minutes = 0
        if on_way_at and arrived_at and arrived_at >= on_way_at:
            travel_minutes = int((arrived_at - on_way_at).total_seconds() // 60)

        work_minutes = 0
        if in_progress_at and completed_at and completed_at >= in_progress_at:
            work_minutes = int((completed_at - in_progress_at).total_seconds() // 60)

        bucket = rows_by_worker.setdefault(
            worker_name,
            {
                "worker_name": worker_name,
                "requests_count": 0,
                "travel_minutes": 0,
                "work_minutes": 0,
            },
        )
        bucket["requests_count"] += 1
        bucket["travel_minutes"] += travel_minutes
        bucket["work_minutes"] += work_minutes

    rows = sorted(
        rows_by_worker.values(),
        key=lambda r: (r["work_minutes"] + r["travel_minutes"], r["worker_name"]),
        reverse=True,
    )

    total_travel_minutes = sum(r["travel_minutes"] for r in rows)
    total_work_minutes = sum(r["work_minutes"] for r in rows)

    for row in rows:
        row["total_minutes"] = row["travel_minutes"] + row["work_minutes"]
        row["travel_human"] = format_minutes(row["travel_minutes"])
        row["work_human"] = format_minutes(row["work_minutes"])
        row["total_human"] = format_minutes(row["total_minutes"])

    totals = {
        "travel_minutes": total_travel_minutes,
        "work_minutes": total_work_minutes,
        "total_minutes": total_travel_minutes + total_work_minutes,
        "travel_human": format_minutes(total_travel_minutes),
        "work_human": format_minutes(total_work_minutes),
        "total_human": format_minutes(total_travel_minutes + total_work_minutes),
    }
    return rows, totals
