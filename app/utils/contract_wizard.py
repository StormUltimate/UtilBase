"""Мастер договора на обслуживание: расчёт сумм, развёртка перечня, проверка топлива."""

from __future__ import annotations

import calendar
import json
import uuid
from datetime import date, datetime
from typing import Any

# Категории оборудования (ключ → подпись)
EQUIPMENT_CATEGORY_LABELS = {
    "hvo": "Системы ХВО (фильтры)",
    "heating": "Системы отопления",
    "boiler": "Бойлеры / котлы",
    "ventilation": "Вентиляция",
    "other": "Прочее",
}

# Виды работ по умолчанию (код → подпись)
DEFAULT_WORK_KINDS = {
    "TO": "ТО — техническое обслуживание",
    "TR": "ТР — текущий ремонт",
    "OTS": "ОТС — оперативно-техническое сопровождение",
    "PPS": "ППС — планово-предупредительный сервис",
    "PNR": "ПНР — пуско-наладочные работы",
}

FREQUENCY_MONTHLY = "monthly"
FREQUENCY_QUARTERLY = "quarterly"
FREQUENCY_SEMIANNUAL = "semiannual"
FREQUENCY_ANNUAL = "annual"
FREQUENCY_CUSTOM_MONTHLY = "custom_monthly"

FREQUENCY_CHOICES = (
    (FREQUENCY_MONTHLY, "1 раз в месяц"),
    (FREQUENCY_QUARTERLY, "1 раз в квартал"),
    (FREQUENCY_SEMIANNUAL, "1 раз в полугодие"),
    (FREQUENCY_ANNUAL, "1 раз в год"),
    (FREQUENCY_CUSTOM_MONTHLY, "Своё: от 1 до 10 раз в месяц"),
)

# Топливо: природный газ запрещён для данного договора
FUEL_NATURAL_GAS = "natural_gas"

FUEL_OPTIONS = (
    ("", "Не указано"),
    ("diesel", "Дизель"),
    ("pellets", "Пеллеты"),
    ("fuel_oil", "Мазут"),
    ("electric", "Электричество"),
    ("other", "Другое"),
    (FUEL_NATURAL_GAS, "Природный газ (только региональная служба — недопустимо)"),
)


def validate_wizard_for_final(wizard: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if not wizard.get("client_id"):
        errs.append("Выберите заказчика из базы.")
    c = wizard.get("contract") or {}
    if not (c.get("contract_type") or "").strip():
        errs.append("Укажите тип / системы по договору.")
    start, end = dates_from_wizard(wizard)
    if not start or not end:
        errs.append("Укажите даты начала и окончания действия договора.")
    elif end < start:
        errs.append("Дата окончания не может быть раньше даты начала.")
    if has_forbidden_gas(wizard):
        errs.append(
            "Выбрано топливо «природный газ». Обслуживание газового оборудования не выполняется "
            "(только региональная служба). Измените топливо или удалите позицию."
        )
    eqs = wizard.get("equipment") or []
    if not eqs:
        errs.append("Добавьте хотя бы одну единицу оборудования.")
    for i, eq in enumerate(eqs):
        label = (eq.get("title") or f"Позиция {i + 1}").strip()
        if not (eq.get("title") or "").strip():
            errs.append(f"{label}: укажите наименование / тип / модель.")
        if equipment_requires_fuel(eq):
            if not (eq.get("fuel") or "").strip():
                errs.append(f"{label}: для котлов/бойлеров укажите тип топлива.")
            elif eq.get("fuel") == FUEL_NATURAL_GAS:
                errs.append(
                    f"{label}: природный газ не допускается — выберите другое топливо или исключите позицию."
                )
        wls = eq.get("work_lines") or []
        if not wls:
            errs.append(f"{label}: добавьте хотя бы один вид работ с ценой и периодичностью.")
        for wl in wls:
            if float(wl.get("price_per_visit") or 0) < 0:
                errs.append(f"{label}: цена за раз не может быть отрицательной.")
            if not _safe_parse_iso_date(wl.get("start_date")):
                errs.append(f"{label}: для каждой строки обслуживания укажите дату.")
    return errs


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    last = calendar.monthrange(y, m)[1]
    day = min(d.day, last)
    return date(y, m, day)


def months_inclusive(start: date, end: date) -> int:
    if end < start:
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def visits_per_year(frequency: str, custom_times_per_month: int) -> float:
    if frequency == FREQUENCY_MONTHLY:
        return 12.0
    if frequency == FREQUENCY_QUARTERLY:
        return 4.0
    if frequency == FREQUENCY_SEMIANNUAL:
        return 2.0
    if frequency == FREQUENCY_ANNUAL:
        return 1.0
    if frequency == FREQUENCY_CUSTOM_MONTHLY:
        n = max(1, min(10, int(custom_times_per_month or 1)))
        return 12.0 * n
    return 12.0


def count_visits_in_period(
    start: date, end: date, frequency: str, custom_times_per_month: int
) -> int:
    """Число выполнений услуги за период [start, end] по правилу периодичности."""
    if end < start:
        return 0
    if frequency == FREQUENCY_CUSTOM_MONTHLY:
        n = max(1, min(10, int(custom_times_per_month or 1)))
        return months_inclusive(start, end) * n

    dates = list(iter_service_dates(start, end, frequency, custom_times_per_month))
    return len(dates)


def _safe_parse_iso_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def iter_service_dates(
    start: date,
    end: date,
    frequency: str,
    custom_times_per_month: int,
    month_days: list[int] | None = None,
) -> list[date]:
    out: list[date] = []
    if end < start:
        return out

    if frequency == FREQUENCY_CUSTOM_MONTHLY:
        n = max(1, min(10, int(custom_times_per_month or 1)))
        cur = date(start.year, start.month, 1)
        selected_days = sorted(
            {max(1, min(31, int(x))) for x in (month_days or []) if str(x).strip()}
        )
        while cur <= end:
            last_day = calendar.monthrange(cur.year, cur.month)[1]
            if selected_days:
                days_sel = [min(last_day, d) for d in selected_days[:n]]
                if len(days_sel) < n:
                    for i in range(len(days_sel), n):
                        auto_d = min(last_day, 1 + int((i + 1) * last_day / (n + 1)))
                        days_sel.append(auto_d)
            else:
                days_sel = [min(last_day, 1 + int((i + 1) * last_day / (n + 1))) for i in range(n)]
            for day in sorted(set(days_sel)):
                try:
                    d = date(cur.year, cur.month, day)
                except ValueError:
                    continue
                if start <= d <= end:
                    out.append(d)
            cur = add_months(cur, 1)
        out.sort()
        return out

    step_months = {
        FREQUENCY_MONTHLY: 1,
        FREQUENCY_QUARTERLY: 3,
        FREQUENCY_SEMIANNUAL: 6,
        FREQUENCY_ANNUAL: 12,
    }.get(frequency, 1)

    d = start
    while d <= end:
        out.append(d)
        d = add_months(d, step_months)
    return out


def line_total_price(
    price_per_visit: float,
    start: date,
    end: date,
    frequency: str,
    custom_times_per_month: int,
) -> float:
    # В текущем мастере 1 строка обслуживания = 1 запланированный выезд.
    return round(float(price_per_visit or 0), 2)


def wizard_payload_total(wizard: dict[str, Any], start: date, end: date) -> float:
    total = 0.0
    for eq in wizard.get("equipment") or []:
        for wl in eq.get("work_lines") or []:
            total += float(wl.get("price_per_visit") or 0)
    return round(total, 2)


def equipment_requires_fuel(eq: dict[str, Any]) -> bool:
    cat = (eq.get("category") or "").strip()
    if cat == "boiler":
        return True
    title = ((eq.get("title") or "") + (eq.get("type_name") or "")).lower()
    for kw in ("котел", "котёл", "бойлер"):
        if kw in title:
            return True
    return False


def has_forbidden_gas(wizard: dict[str, Any]) -> bool:
    for eq in wizard.get("equipment") or []:
        fuel = (eq.get("fuel") or "").strip()
        if fuel == FUEL_NATURAL_GAS:
            return True
    return False


def expand_wizard_to_scope_rows(
    wizard: dict[str, Any],
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """Перечень позиций для equipment_scope и синхронизации заявок."""
    rows: list[dict[str, Any]] = []
    for eq in wizard.get("equipment") or []:
        eq_label = (eq.get("title") or eq.get("type_name") or "Оборудование").strip()
        cat_label = EQUIPMENT_CATEGORY_LABELS.get(
            eq.get("category") or "", eq.get("category") or ""
        )
        name_base = f"{eq_label}" + (f" ({cat_label})" if cat_label else "")

        for wl in eq.get("work_lines") or []:
            wcode = (wl.get("work_kind") or "").strip()
            custom_w = (wl.get("work_kind_custom") or "").strip()
            if wcode == "OTHER" and custom_w:
                service_kind = custom_w
            elif wcode and wcode in DEFAULT_WORK_KINDS:
                lab = DEFAULT_WORK_KINDS[wcode]
                service_kind = lab
                for sep in ("—", "–", "-"):
                    if sep in lab:
                        service_kind = lab.split(sep, 1)[0].strip()
                        break
            elif wcode:
                service_kind = wcode
            else:
                continue

            freq = str(wl.get("frequency") or FREQUENCY_MONTHLY)
            price = float(wl.get("price_per_visit") or 0)
            line_start = _safe_parse_iso_date(wl.get("start_date")) or start
            if line_start < start:
                line_start = start
            if line_start > end:
                continue
            uid = uuid.uuid4().hex
            rows.append(
                {
                    "uid": uid,
                    "name": f"{name_base} — {service_kind}",
                    "service_kind": service_kind,
                    "planned_date": line_start.isoformat(),
                    "price": round(price, 2),
                    "done_manual": False,
                    "request_id": None,
                }
            )
    return rows


def parse_wizard_json(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def merge_payment_terms_note(wizard: dict[str, Any]) -> str:
    pt = (wizard.get("contract") or {}).get("payment_terms") or "acts"
    labels = {
        "prepaid": "Оплата: предоплата",
        "acts": "Оплата: по актам выполненных работ",
        "other": "Оплата: иные условия",
    }
    base = labels.get(pt, labels["acts"])
    note = ((wizard.get("contract") or {}).get("payment_terms_note") or "").strip()
    if note:
        return f"{base}. {note}"
    return base


def build_service_periodicity_summary(wizard: dict[str, Any]) -> str:
    lines: list[str] = []
    for eq in wizard.get("equipment") or []:
        label = (eq.get("title") or "Узел").strip()
        for wl in eq.get("work_lines") or []:
            wk = (wl.get("work_kind") or "").strip()
            dt = str(wl.get("start_date") or "").strip()
            date_part = f"дата {dt}" if dt else "дата не указана"
            lines.append(
                f"{label}: {wk}, {date_part}, {float(wl.get('price_per_visit') or 0):,.0f} ₽".replace(
                    ",", " "
                )
            )
    return "\n".join(lines) if lines else ""


def default_wizard(client_id: int | None = None) -> dict[str, Any]:
    today = date.today()
    end = add_months(today, 12)
    return {
        "version": 1,
        "client_id": client_id,
        "counterparty_kind": "",
        "client_snapshot": {
            "legal_name": "",
            "inn": "",
            "kpp": "",
            "ogrn": "",
            "legal_address": "",
            "actual_address": "",
            "contact_person": "",
            "phone": "",
            "email": "",
            "bank_details": "",
        },
        "service_object_address": "",
        "use_client_address": True,
        "contract": {
            "contract_type": "комплексный",
            "document_number": "",
            "conclusion_date": today.isoformat(),
            "start_date": today.isoformat(),
            "end_date": end.isoformat(),
            "payment_terms": "acts",
            "payment_terms_note": "",
            "term_note": "",
        },
        "equipment": [],
    }


def dates_from_wizard(wizard: dict[str, Any]) -> tuple[date | None, date | None]:
    c = wizard.get("contract") or {}
    sd = c.get("start_date")
    ed = c.get("end_date")
    try:
        start = datetime.strptime(str(sd)[:10], "%Y-%m-%d").date() if sd else None
    except ValueError:
        start = None
    try:
        end = datetime.strptime(str(ed)[:10], "%Y-%m-%d").date() if ed else None
    except ValueError:
        end = None
    return start, end
