# Path: app/utils/telegram_logger.py
from datetime import datetime

from app.extensions import db
from app.models.all_models import SystemLogs


def log_telegram_action(level: str, message: str, user_id=None):
    """Запись в system_logs (как в старом SpasatelWeb log_action)."""
    try:
        db.session.add(
            SystemLogs(
                created_at=datetime.now(),
                level=level,
                message=message,
            )
        )
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
