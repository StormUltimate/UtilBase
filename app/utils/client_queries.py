"""Поиск клиентов для подбора (ФИО, телефон, адрес) и фильтр по виду."""

from sqlalchemy import case, func, nullslast, or_

from app.models.all_models import Client
from app.utils.client_kinds import CLIENT_KIND_KEYS, client_kind_label


def search_clients_for_picker(q: str, kind: str | None, limit: int = 20):
    """
    q — строка поиска (минимум 1 символ), либо пусто — тогда первые N клиентов (или по виду).
    kind — '', '__none__', или ключ из CLIENT_KIND_KEYS.
    """
    q = (q or "").strip()
    limit = max(1, min(int(limit or 20), 50))
    query = Client.query
    kind = (kind or "").strip()

    if kind == "__none__":
        query = query.filter(Client.client_kind.is_(None))
    elif kind in CLIENT_KIND_KEYS:
        query = query.filter(Client.client_kind == kind)

    if len(q) >= 1:
        ql = q.lower()
        term = f"%{q}%"
        query = query.filter(
            or_(
                Client.full_name.ilike(term),
                Client.phone.ilike(term),
                Client.address.ilike(term),
            )
        )
        # Ранжирование: сначала точное/префиксное совпадение, затем остальные.
        rank_expr = case(
            (func.lower(Client.phone) == ql, 0),
            (func.lower(Client.full_name) == ql, 1),
            (func.lower(Client.phone).like(f"{ql}%"), 2),
            (func.lower(Client.full_name).like(f"{ql}%"), 3),
            (func.lower(Client.address).like(f"{ql}%"), 4),
            else_=5,
        )
        query = query.order_by(rank_expr.asc(), nullslast(Client.full_name.asc()), Client.id.asc())
    else:
        # Пустой ввод: отдаем первые N клиентов (или выбранного вида),
        # чтобы пользователь видел варианты и мог выбрать из списка.
        query = query.order_by(nullslast(Client.full_name.asc()), Client.id.asc())

    rows = query.limit(limit).all()
    return rows


def clients_to_json_results(clients: list):
    out = []
    for c in clients:
        parts = [c.full_name or "Без имени", c.phone or "—", (c.address or "")[:80]]
        text = f"{parts[0]} · {parts[1]} · {parts[2]}"
        out.append(
            {
                "id": c.id,
                "text": text,
                "label": text,
                "full_name": c.full_name or "",
                "phone": c.phone or "",
                "address": c.address or "",
                "kind": getattr(c, "client_kind", None) or "",
                "kind_label": client_kind_label(getattr(c, "client_kind", None)),
            }
        )
    return out
