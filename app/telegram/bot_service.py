# Path: app/telegram/bot_service.py
"""Telegram-бот: загрузка фото/видео/документов из групп и каналов в таблицу media."""

from __future__ import annotations

import logging
import os
from collections import deque
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.extensions import db
from app.models.all_models import Media, TelegramBotUsers, TelegramChat, TelegramMessage

logger = logging.getLogger(__name__)

MAX_FILES_PER_HOUR = 50
_file_counts: dict[str, dict] = {}
NOTIFICATIONS: deque = deque(maxlen=100)
BOT_RUNNING = True

_chat_ids_seen: set[str] = set()


def _admin_ids(app) -> set[str]:
    raw = (app.config.get("TELEGRAM_ADMIN_IDS") or os.getenv("TELEGRAM_ADMIN_IDS") or "").strip()
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


def add_notification(message: str) -> None:
    NOTIFICATIONS.append(
        {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "message": message}
    )
    logger.info(message)


def _check_download_limit(chat_id: str) -> bool:
    now = datetime.now()
    if chat_id not in _file_counts:
        _file_counts[chat_id] = {"count": 0, "last_reset": now}
    if (now - _file_counts[chat_id]["last_reset"]).total_seconds() > 3600:
        _file_counts[chat_id] = {"count": 0, "last_reset": now}
    if _file_counts[chat_id]["count"] >= MAX_FILES_PER_HOUR:
        logger.warning("Лимит скачиваний (%s) для чата %s", MAX_FILES_PER_HOUR, chat_id)
        add_notification(f"⛔ Достигнут лимит скачиваний ({MAX_FILES_PER_HOUR}) для чата {chat_id}")
        return False
    _file_counts[chat_id]["count"] += 1
    return True


def _ensure_chat_row(app, chat_id: str, title: str | None) -> None:
    with app.app_context():
        row = TelegramChat.query.filter_by(chat_id=chat_id).first()
        if row:
            if title and title != row.title:
                row.title = title
                row.updated_at = datetime.utcnow()
                db.session.commit()
            return
        db.session.add(
            TelegramChat(
                chat_id=chat_id,
                title=title or chat_id,
                download_enabled=False,
                is_favorite=False,
                created_at=datetime.utcnow(),
            )
        )
        db.session.commit()


def is_download_enabled(app, chat_id: str) -> bool:
    with app.app_context():
        row = TelegramChat.query.filter_by(chat_id=chat_id).first()
        return bool(row and row.download_enabled)


def save_message_to_db(
    app,
    sender_name: str,
    message_text: str,
    message_dt: datetime,
    telegram_message_id: int,
    chat_id: str,
) -> None:
    with app.app_context():
        try:
            db.session.add(
                TelegramMessage(
                    sender=sender_name,
                    message_text=message_text,
                    message_date=message_dt,
                    telegram_message_id=telegram_message_id,
                    chat_id=chat_id,
                )
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        except Exception as e:
            db.session.rollback()
            logger.error("Ошибка записи telegram_messages: %s", e)


def save_media_to_db(
    app,
    relative_path: str,
    media_type: str,
    sender_name: str,
    telegram_id: int | None,
    message_dt: datetime,
    description: str | None,
    chat_id: str,
    telegram_message_id: int | None = None,
) -> None:
    with app.app_context():
        try:
            uid = None
            if telegram_id is not None:
                link = TelegramBotUsers.query.filter_by(telegram_id=str(telegram_id)).first()
                if link:
                    uid = link.user_id
            m = Media(
                file_path=relative_path.replace("\\", "/"),
                file_type=media_type,
                upload_date=message_dt,
                description=description,
                created_by_user_id=uid,
                chat_id=chat_id,
                author_name=sender_name,
                telegram_message_id=telegram_message_id,
            )
            db.session.add(m)
            db.session.commit()
            logger.info("Медиа сохранено: %s", relative_path)
        except Exception as e:
            db.session.rollback()
            logger.error("Ошибка записи media: %s", e)
            add_notification(f"❌ Ошибка при записи файла в БД: {e}")


def _static_fs_dir(app, *parts: str) -> str:
    return os.path.join(app.root_path, "static", *parts)


def _msg_time(msg) -> datetime:
    if not msg.date:
        return datetime.utcnow()
    if msg.date.tzinfo:
        return msg.date.astimezone(timezone.utc).replace(tzinfo=None)
    return msg.date


async def _start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    add_notification(
        "🤖 Бот для сохранения медиа и сообщений. Включите скачивание для чата в веб-интерфейсе UtilBase."
    )


async def _stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.bot_data.get("flask_app")
    if not app:
        return
    uid = str(update.effective_user.id) if update.effective_user else ""
    if uid not in _admin_ids(app):
        return
    with app.app_context():
        from sqlalchemy import func

        rows = (
            db.session.query(Media.file_type, func.count(Media.id))
            .filter(
                Media.chat_id.isnot(None),
            )
            .group_by(Media.file_type)
            .all()
        )
    total = sum(c for _, c in rows)
    lines = [f"📊 Файлов из Telegram (по типам). Всего: {total}"]
    for ft, c in rows:
        lines.append(f"{ft}: {c}")
    add_notification("\n".join(lines))


async def _channels_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.bot_data.get("flask_app")
    if not app:
        return
    uid = str(update.effective_user.id) if update.effective_user else ""
    if uid not in _admin_ids(app):
        return
    with app.app_context():
        rows = TelegramChat.query.order_by(TelegramChat.title).all()
    lines = ["📋 Чаты в базе:"]
    for r in rows:
        lines.append(
            f"ID: {r.chat_id}, {r.title or '?'} — скачивание: "
            f"{'вкл' if r.download_enabled else 'выкл'}"
        )
    add_notification("\n".join(lines))


async def _handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not BOT_RUNNING:
        return
    app = context.bot_data.get("flask_app")
    if not app:
        return
    msg = update.effective_message
    if not msg or not msg.text:
        return
    chat_id = str(msg.chat_id)
    _chat_ids_seen.add(chat_id)
    try:
        title = msg.chat.title if getattr(msg.chat, "title", None) else None
        _ensure_chat_row(app, chat_id, title)
    except Exception as e:
        logger.warning("ensure_chat_row: %s", e)

    sender = msg.from_user
    sender_name = (
        sender.full_name if sender else (msg.sender_chat.title if msg.sender_chat else "Unknown")
    )
    message_dt = _msg_time(msg)
    save_message_to_db(
        app,
        sender_name,
        msg.text,
        message_dt,
        msg.message_id,
        chat_id,
    )


async def _handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not BOT_RUNNING:
        return
    app = context.bot_data.get("flask_app")
    if not app:
        return
    msg = update.effective_message
    if not msg:
        return
    chat_id = str(msg.chat_id)
    _chat_ids_seen.add(chat_id)
    try:
        title = msg.chat.title if getattr(msg.chat, "title", None) else None
        _ensure_chat_row(app, chat_id, title)
    except Exception as e:
        logger.warning("ensure_chat_row: %s", e)

    if not is_download_enabled(app, chat_id):
        logger.info("Скачивание выключено для чата %s", chat_id)
        return
    if not _check_download_limit(chat_id):
        return

    sender = msg.from_user
    sender_name = (
        sender.full_name if sender else (msg.sender_chat.title if msg.sender_chat else "Unknown")
    )
    telegram_id = sender.id if sender else None
    message_dt = _msg_time(msg)
    caption = msg.caption

    channel_media_dir = _static_fs_dir(app, "media", f"channel_{chat_id}")
    channel_docs_dir = _static_fs_dir(app, "documents", f"channel_{chat_id}")
    os.makedirs(channel_media_dir, exist_ok=True)
    os.makedirs(channel_docs_dir, exist_ok=True)

    try:
        if msg.photo:
            media_type = "photo"
            file = await msg.photo[-1].get_file()
            fname = f"photo_{msg.message_id}.jpg"
            fs_path = os.path.join(channel_media_dir, fname)
            rel = "/".join(["media", f"channel_{chat_id}", fname])
            await file.download_to_drive(fs_path)
        elif msg.video:
            media_type = "video"
            file = await msg.video.get_file()
            fname = f"video_{msg.message_id}.mp4"
            fs_path = os.path.join(channel_media_dir, fname)
            rel = "/".join(["media", f"channel_{chat_id}", fname])
            await file.download_to_drive(fs_path)
        elif msg.document:
            media_type = "document"
            file = await msg.document.get_file()
            ext = os.path.splitext(file.file_path or "")[1] or ""
            fname = f"document_{msg.message_id}{ext}"
            fs_path = os.path.join(channel_docs_dir, fname)
            rel = "/".join(["documents", f"channel_{chat_id}", fname])
            await file.download_to_drive(fs_path)
        else:
            return

        save_media_to_db(
            app,
            rel,
            media_type,
            sender_name,
            telegram_id,
            message_dt,
            caption,
            chat_id,
            telegram_message_id=msg.message_id,
        )
        add_notification(f"📥 Скачан файл ({media_type}) в {rel}")
    except Exception as e:
        logger.exception("Ошибка обработки медиа: %s", e)
        add_notification(f"❌ Ошибка медиа в чате {chat_id}: {e}")


def run_telegram_bot(app) -> None:
    """Запуск polling (блокирует поток). Вызывать внутри app.app_context() или из worker-процесса."""
    token = (app.config.get("BOT_TOKEN") or "").strip()
    if not token or len(token) < 30:
        logger.error("BOT_TOKEN не задан или слишком короткий — проверьте .env")
        return

    log_path = app.config.get("LOG_FILE") or os.path.join(app.config["BASE_DIR"], "logs", "bot.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )

    application = Application.builder().token(token).build()
    application.bot_data["flask_app"] = app

    application.add_handler(CommandHandler("start", _start_cmd))
    application.add_handler(CommandHandler("stats", _stats_cmd))
    application.add_handler(CommandHandler("channels", _channels_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text))
    application.add_handler(
        MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, _handle_media)
    )

    logger.info("Telegram-бот: polling…")
    application.run_polling(drop_pending_updates=True)
