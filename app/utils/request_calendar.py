# Path: app/utils/request_calendar.py
"""Общая логика интервалов планирования заявки для календарей (заявки и исполнители)."""

from datetime import datetime, time, timedelta

# Дефолтный «график» смены для заливки слоя календаря (аналог рабочего дня; не Google Calendar).
SHIFT_DAY_START = time(9, 0)
SHIFT_DAY_END = time(19, 0)


def parse_fc_iso(s: str) -> datetime:
    """ISO из FullCalendar (может заканчиваться на Z). В БД храним naive datetime."""
    if not s:
        raise ValueError("empty datetime")
    raw = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


WORKER_CAL_COLORS = [
    "#0d6efd",
    "#198754",
    "#fd7e14",
    "#6f42c1",
    "#d63384",
    "#20c997",
    "#6610f2",
    "#dc3545",
    "#0dcaf0",
]


def worker_calendar_color(worker_id: int) -> str:
    return WORKER_CAL_COLORS[worker_id % len(WORKER_CAL_COLORS)]


def worker_display_color(worker) -> str:
    """Цвет из Worker.color или fallback по id."""
    if worker is None:
        return WORKER_CAL_COLORS[0]
    raw = getattr(worker, "color", None)
    if isinstance(raw, str) and raw.strip().startswith("#") and len(raw.strip()) >= 4:
        return raw.strip()
    return worker_calendar_color(worker.id)


def hex_to_rgba_background(hex_color: str, alpha: float = 0.14) -> str:
    if hex_color.startswith("#") and len(hex_color) >= 7:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        return f"rgba({r},{g},{b},{alpha})"
    return f"rgba(25, 135, 84, {alpha})"


def shift_layer_events_from_db(shifts) -> list:
    """shifts: iterable WorkerShift с загруженным .worker — полосы смен (не background, чтобы FC раскладывал их в колонки)."""
    out = []
    for s in shifts:
        start = datetime.combine(s.shift_date, s.time_start)
        end = datetime.combine(s.shift_date, s.time_end)
        if end <= start:
            end = start + timedelta(hours=1)
        hc = worker_display_color(s.worker)
        name = (s.worker.full_name if s.worker else "") or "—"
        out.append(
            {
                "id": f"shift-{s.id}",
                "title": name,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "allDay": False,
                "backgroundColor": hex_to_rgba_background(hc, 0.42),
                "borderColor": hc,
                "textColor": "#1a1d20",
                "classNames": ["fc-worker-shift-slab"],
                "extendedProps": {
                    "layer": "shift",
                    "workerId": s.worker_id,
                    "workerName": name,
                },
            }
        )
    return out


def shift_background_events(start_iso: str, end_iso: str) -> list:
    """
    Устаревший общий фон по дням без привязки к исполнителю.
    Оставлен как запасной вариант; основной слой — shift_layer_events_from_db.
    """
    start = parse_fc_iso(start_iso)
    end = parse_fc_iso(end_iso)
    out = []
    d = start.date()
    end_d = end.date()
    while d < end_d:
        t0 = datetime.combine(d, SHIFT_DAY_START)
        t1 = datetime.combine(d, SHIFT_DAY_END)
        out.append(
            {
                "id": f"shift-bg-{d.isoformat()}",
                "start": t0.isoformat(),
                "end": t1.isoformat(),
                "display": "background",
                "backgroundColor": "rgba(25, 135, 84, 0.09)",
                "borderColor": "transparent",
                "extendedProps": {"layer": "shift"},
            }
        )
        d += timedelta(days=1)
    return out


def planned_range_for_request(req):
    """
    Интервал start/end для FullCalendar (нужны datetime, не только дата).
    """
    if not req.planned_date:
        return None, None
    if req.planned_start_time:
        start = req.planned_start_time
        if req.planned_end_time:
            end = req.planned_end_time
        else:
            end = start + timedelta(hours=2)
        return start, end
    d = req.planned_date
    start = datetime.combine(d, time(9, 0))
    end = datetime.combine(d, time(11, 0))
    return start, end
