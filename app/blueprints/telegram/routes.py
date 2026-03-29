# Path: app/blueprints/telegram/routes.py
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from functools import wraps

import psutil
from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.all_models import TelegramChat
from app.utils.telegram_logger import log_telegram_action

telegram_bp = Blueprint("telegram", __name__, url_prefix="/telegram-bot")

bot_process = None
log_queue = queue.Queue()
SCAN_COOLDOWN = 60
last_scan_time = 0


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            if request.is_json or request.path.endswith(("status", "logs")):
                return jsonify(
                    {"status": "error", "message": "Доступ только для администратора"}
                ), 403
            return "Доступ запрещён", 403
        return f(*args, **kwargs)

    return wrapped


def _project_root():
    return os.path.abspath(os.path.join(current_app.root_path, ".."))


def _worker_script():
    return os.path.join(_project_root(), "telegram_bot_worker.py")


def _read_last_log_lines(n=80):
    log_path = current_app.config.get("LOG_FILE")
    if not log_path or not os.path.isfile(log_path):
        log_path = os.path.join(_project_root(), "logs", "bot.log")
    try:
        with open(log_path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return [{"type": "info", "message": ln.rstrip()} for ln in lines[-n:]]
    except OSError:
        return []


def is_bot_running():
    global bot_process
    if bot_process is None:
        return False
    try:
        p = psutil.Process(bot_process.pid)
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def read_process_output(process, q):
    while True:
        try:
            line = process.stdout.readline() if process.stdout else ""
            if line:
                q.put({"type": "info", "message": line.strip()})
            if process.poll() is not None:
                q.put({"type": "info", "message": f"Процесс завершился с кодом {process.poll()}"})
                break
        except Exception as e:
            q.put({"type": "error", "message": f"Ошибка чтения вывода: {e}"})
            break


@telegram_bp.route("/status", methods=["GET"])
@admin_required
def get_status():
    status = is_bot_running()
    return jsonify({"started": status, "running": status})


@telegram_bp.route("/logs", methods=["GET"])
@admin_required
def get_logs():
    logs = []
    while not log_queue.empty():
        try:
            logs.append(log_queue.get_nowait())
        except queue.Empty:
            break
    if not logs:
        logs = _read_last_log_lines()
    return jsonify({"logs": logs})


@telegram_bp.route("/", methods=["GET"])
@admin_required
def bot_control():
    channels = []
    rows = TelegramChat.query.order_by(TelegramChat.is_favorite.desc(), TelegramChat.title).all()
    for r in rows:
        channels.append(
            {
                "chat_id": r.chat_id,
                "title": r.title or "",
                "download_enabled": r.download_enabled,
                "is_favorite": r.is_favorite,
            }
        )
    return render_template(
        "telegram/telegram_bot_control.html",
        channels=channels,
        notifications=[],
        bot_started=is_bot_running(),
    )


@telegram_bp.route("/start-bot", methods=["POST"])
@admin_required
def start_bot():
    global bot_process
    if is_bot_running():
        return jsonify({"status": "error", "message": "Бот уже запущен"})

    token = (current_app.config.get("BOT_TOKEN") or "").strip()
    if not token or len(token) < 30:
        return jsonify({"status": "error", "message": "Укажите BOT_TOKEN в .env"})

    script = _worker_script()
    if not os.path.isfile(script):
        return jsonify({"status": "error", "message": f"Не найден {script}"})

    try:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        bot_process = subprocess.Popen(
            [sys.executable, script],
            cwd=_project_root(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        threading.Thread(
            target=read_process_output, args=(bot_process, log_queue), daemon=True
        ).start()
        time.sleep(1)
        if bot_process.poll() is not None:
            out, err = bot_process.communicate(timeout=5)
            bot_process = None
            msg = (err or out or "Неизвестная ошибка").strip()
            return jsonify({"status": "error", "message": f"Бот завершился: {msg[:500]}"})

        log_telegram_action(
            "INFO",
            f"Telegram-бот запущен из веб-интерфейса, PID {bot_process.pid}",
            current_user.id,
        )
        return jsonify({"status": "success", "message": "Бот запущен", "pid": bot_process.pid})
    except Exception as e:
        bot_process = None
        return jsonify({"status": "error", "message": str(e)})


@telegram_bp.route("/stop-bot", methods=["POST"])
@admin_required
def stop_bot():
    global bot_process
    if not is_bot_running():
        return jsonify({"status": "error", "message": "Бот не запущен"})
    try:
        proc = psutil.Process(bot_process.pid)
        proc.terminate()
        proc.wait(timeout=8)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally:
        bot_process = None
    log_telegram_action("INFO", "Telegram-бот остановлен из веб-интерфейса", current_user.id)
    return jsonify({"status": "success", "message": "Бот остановлен"})


@telegram_bp.route("/restart-bot", methods=["POST"])
@admin_required
def restart_bot():
    global bot_process
    if is_bot_running():
        try:
            proc = psutil.Process(bot_process.pid)
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            pass
        bot_process = None
    time.sleep(1)
    return start_bot()


@telegram_bp.route("/scan-channels", methods=["GET"])
@admin_required
def scan_channels():
    global last_scan_time
    now = time.time()
    if now - last_scan_time < SCAN_COOLDOWN:
        rem = int(SCAN_COOLDOWN - (now - last_scan_time))
        return jsonify({"status": "error", "message": f"Подождите ещё {rem} с."})

    if not is_bot_running():
        return jsonify({"status": "error", "message": "Сначала запустите бота"})

    last_scan_time = now
    channels = []
    rows = TelegramChat.query.order_by(TelegramChat.title).all()
    for r in rows:
        channels.append(
            {
                "chat_id": r.chat_id,
                "title": r.title or "",
                "download_enabled": r.download_enabled,
                "is_favorite": r.is_favorite,
            }
        )
    log_telegram_action(
        "INFO", f"Сканирование чатов: в базе {len(channels)} записей", current_user.id
    )
    return jsonify(
        {
            "status": "success",
            "message": f"Найдено {len(channels)} чатов в базе",
            "channels": channels,
        }
    )


@telegram_bp.route("/add-chat", methods=["POST"])
@admin_required
def add_chat():
    chat_id = request.form.get("chat_id")
    title = request.form.get("title")
    download_enabled = request.form.get("download_enabled") == "true"
    if not chat_id or not title:
        return jsonify({"status": "error", "message": "Не указан chat_id или название"})

    row = TelegramChat.query.filter_by(chat_id=chat_id).first()
    if row:
        row.title = title
        row.download_enabled = download_enabled
        row.updated_at = datetime.utcnow()
    else:
        db.session.add(
            TelegramChat(
                chat_id=chat_id,
                title=title,
                download_enabled=download_enabled,
                is_favorite=False,
                created_at=datetime.utcnow(),
            )
        )
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)})

    log_telegram_action("INFO", f"Чат Telegram {chat_id} ({title}) сохранён", current_user.id)
    return jsonify(
        {
            "status": "success",
            "message": f"Чат {title} добавлен",
            "chat": {
                "chat_id": chat_id,
                "title": title,
                "download_enabled": download_enabled,
                "is_favorite": False,
            },
        }
    )


@telegram_bp.route("/update-chat-title", methods=["POST"])
@admin_required
def update_chat_title():
    chat_id = request.form.get("chat_id")
    new_title = request.form.get("title")
    if not chat_id or not new_title:
        return jsonify({"status": "error", "message": "Не указан chat_id или название"})

    row = TelegramChat.query.filter_by(chat_id=chat_id).first()
    if not row:
        return jsonify({"status": "error", "message": "Чат не найден"})
    row.title = new_title
    row.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(
        {
            "status": "success",
            "message": "Название обновлено",
            "chat_id": chat_id,
            "title": new_title,
        }
    )


@telegram_bp.route("/remove-chat", methods=["POST"])
@admin_required
def remove_chat():
    chat_id = request.form.get("chat_id")
    if not chat_id:
        return jsonify({"status": "error", "message": "Не указан chat_id"})
    row = TelegramChat.query.filter_by(chat_id=chat_id).first()
    if not row:
        return jsonify({"status": "error", "message": "Чат не найден"})
    db.session.delete(row)
    db.session.commit()
    return jsonify({"status": "success", "message": f"Чат {chat_id} удалён", "chat_id": chat_id})


@telegram_bp.route("/toggle-download", methods=["POST"])
@admin_required
def toggle_download():
    action = request.form.get("action")
    chat_id = request.form.get("chat_id")
    if not chat_id or action not in ("start", "stop"):
        return jsonify({"status": "error", "message": "Неверные параметры"})

    enabled = action == "start"
    row = TelegramChat.query.filter_by(chat_id=chat_id).first()
    if not row:
        return jsonify(
            {
                "status": "error",
                "message": "Чат не найден — добавьте его вручную или дождитесь сообщения от бота",
            }
        )
    row.download_enabled = enabled
    row.updated_at = datetime.utcnow()
    db.session.commit()
    log_telegram_action(
        "INFO", f"Скачивание для {chat_id}: {'вкл' if enabled else 'выкл'}", current_user.id
    )
    return jsonify(
        {
            "status": "success",
            "message": f"Скачивание {'включено' if enabled else 'отключено'}",
            "enabled": enabled,
            "chat_id": chat_id,
        }
    )


@telegram_bp.route("/toggle-favorite", methods=["POST"])
@admin_required
def toggle_favorite():
    action = request.form.get("action")
    chat_id = request.form.get("chat_id")
    if not chat_id or action not in ("add", "remove"):
        return jsonify({"status": "error", "message": "Неверные параметры"})

    is_favorite = action == "add"
    row = TelegramChat.query.filter_by(chat_id=chat_id).first()
    if not row:
        return jsonify({"status": "error", "message": "Чат не найден"})
    row.is_favorite = is_favorite
    if is_favorite:
        row.download_enabled = True
    row.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(
        {
            "status": "success",
            "message": "Избранное обновлено",
            "is_favorite": is_favorite,
            "chat_id": chat_id,
        }
    )
