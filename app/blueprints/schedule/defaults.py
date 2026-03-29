"""Конфигурация план-графика по умолчанию (переопределяется через app.config или контекст шаблона)."""


def schedule_defaults(app=None):
    """Словарь для schedule_config в шаблоне и JSON meta.config."""
    cfg = {
        "slotMinutes": 30,
        "dayStartHour": 6,
        "dayEndHour": 22,
        "timelineHourHeightPx": 48,
        "defaultShiftStart": "09:00",
        "defaultShiftEnd": "19:00",
        "simpleViewHourHeightPx": 36,
        "extendedViewHourHeightPx": 56,
        "brandAccent": "#0d6efd",
    }
    if app is not None:
        cfg["slotMinutes"] = int(app.config.get("SCHEDULE_SLOT_MINUTES", cfg["slotMinutes"]))
        cfg["dayStartHour"] = int(app.config.get("SCHEDULE_DAY_START_HOUR", cfg["dayStartHour"]))
        cfg["dayEndHour"] = int(app.config.get("SCHEDULE_DAY_END_HOUR", cfg["dayEndHour"]))
        cfg["timelineHourHeightPx"] = int(
            app.config.get("SCHEDULE_HOUR_HEIGHT_PX", cfg["timelineHourHeightPx"])
        )
    return cfg
