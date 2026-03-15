# Путь: V:\UtilBase\app\utils\cron_jobs.py
import schedule
import time
import threading
import logging
from app.utils.check_overdue import check_overdue_requests

logger = logging.getLogger(__name__)

def init_cron_jobs(app):
    # Проверка просроченных заявок каждый час
    schedule.every().hour.do(check_overdue_requests)

    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(60)

    # Запускаем расписание в отдельном потоке
    with app.app_context():
        thread = threading.Thread(target=run_schedule)
        thread.daemon = True
        thread.start()
        logger.info("Cron-задачи запущены")