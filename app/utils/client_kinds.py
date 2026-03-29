# Унифицированные значения вида клиента (как у договора counterparty_kind)
CLIENT_KIND_KEYS = (
    "individual",
    "sole_proprietor",
    "legal_entity",
    "commercial_household",
    "government",
)

CLIENT_KIND_LABELS = {
    "individual": "Физ. лицо",
    "sole_proprietor": "ИП",
    "legal_entity": "Юр. лицо",
    "commercial_household": "Комбыт",
    "government": "Госучреждение",
}

# Для форм: (value, label)
CLIENT_KIND_CHOICES = [("", "Не указано")] + [(k, CLIENT_KIND_LABELS[k]) for k in CLIENT_KIND_KEYS]

CLIENT_KIND_FILTER_CHOICES = [("", "Все"), ("__none__", "Без вида")] + [
    (k, CLIENT_KIND_LABELS[k]) for k in CLIENT_KIND_KEYS
]


def client_kind_label(kind: str | None) -> str:
    if not kind:
        return "—"
    return CLIENT_KIND_LABELS.get(kind, kind)
