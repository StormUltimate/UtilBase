# Путь: V:\UtilBase\app\utils\check_overdue.py
import logging
from datetime import date, datetime

import requests

from app import create_app
from app.config import Config
from app.extensions import db
from app.models.all_models import Request, RequestStatus, SystemLogs

logger = logging.getLogger(__name__)


def check_overdue_requests():
    """Проверка просроченных заявок (cron). Логика совпадает с веб-синхронизацией заявок."""
    app = create_app()
    with app.app_context():
        try:
            overdue_requests = Request.query.filter(
                Request.planned_date < date.today(),
                Request.status.notin_(
                    [RequestStatus.closed, RequestStatus.overdue, RequestStatus.cancelled]
                ),
            ).all()

            if not overdue_requests:
                logger.info("Нет новых просроченных заявок")
                return

            for req in overdue_requests:
                req.status = RequestStatus.overdue
                logger.info(
                    "Заявка ID=%s (№%s) помечена как просроченная",
                    req.id,
                    req.request_number,
                )
                db.session.add(
                    SystemLogs(
                        created_at=datetime.now(),
                        level="INFO",
                        message=f"Заявка ID={req.id} (№{req.request_number}) помечена как просроченная",
                    )
                )
                send_telegram_notification(req.id, req.request_number)

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            logger.error("Ошибка при проверке просроченных заявок: %s", e)
            try:
                db.session.add(
                    SystemLogs(
                        created_at=datetime.now(),
                        level="ERROR",
                        message=f"Ошибка при проверке просроченных заявок: {e!s}",
                    )
                )
                db.session.commit()
            except Exception:
                db.session.rollback()


def send_telegram_notification(request_id, request_number):
    bot_token = Config.BOT_TOKEN
    if not bot_token:
        logger.error("Токен Telegram-бота не настроен")
        return

    chat_id = "YOUR_CHAT_ID"
    message = f"⚠️ Заявка №{request_number} (ID={request_id}) просрочена!"

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logger.info("Уведомление о просроченной заявке ID=%s отправлено в Telegram", request_id)
        else:
            logger.error("Ошибка отправки уведомления в Telegram: %s", response.text)
    except Exception as e:
        logger.error("Ошибка при отправке уведомления в Telegram: %s", e)
