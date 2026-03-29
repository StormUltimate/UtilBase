# Path: app/utils/telegram_export.py
"""Разбор полей экспорта Telegram Desktop (JSON).

Идея извлечения текста из смешанного массива text — как в проекте
docs/telegram-json-ui (extract_text в index.svelte): в дампе text может быть
строкой или списком строк и объектов вида {"type": "bold", "text": "..."}.
"""


def telegram_export_text_to_plain(text) -> str:
    """Плоский текст сообщения для поиска и поля description в БД."""
    if text is None:
        return ""
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        return "".join(_telegram_text_fragment(e) for e in text)
    if isinstance(text, dict):
        inner = text.get("text")
        if inner is not None:
            return telegram_export_text_to_plain(inner)
        return ""
    return str(text)


def _telegram_text_fragment(e) -> str:
    if isinstance(e, str):
        return e
    if isinstance(e, dict):
        t = e.get("text")
        if isinstance(t, str):
            return t
        if t is not None:
            return telegram_export_text_to_plain(t)
        return ""
    return str(e)
