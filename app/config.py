# Path: app/config.py
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Всегда грузим .env из корня проекта (рядом с run.py), а не из текущей cwd.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Config:
    # Лимит тела запроса (импорт JSON из браузера). Для очень больших result.json используйте путь к файлу на сервере.
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "512")) * 1024 * 1024
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        "postgresql://postgres:asdf1234@localhost:5432/utilbase",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-jwt-secret-key")
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    API_FORCE_HTTPS = os.getenv("API_FORCE_HTTPS", "false").lower() in ("1", "true", "yes")
    PREFERRED_URL_SCHEME = "https" if API_FORCE_HTTPS else "http"
    SESSION_COOKIE_SECURE = API_FORCE_HTTPS
    REMEMBER_COOKIE_SECURE = API_FORCE_HTTPS
    # API v1 (мобилка)
    API_ALLOW_UNASSIGNED_POOL = os.getenv("API_ALLOW_UNASSIGNED_POOL", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    API_CLOSE_REQUIRES_COMPLETED_MODE = os.getenv(
        "API_CLOSE_REQUIRES_COMPLETED_MODE", "true"
    ).lower() in ("1", "true", "yes")
    API_CLOSE_MIN_PHOTOS = int(os.getenv("API_CLOSE_MIN_PHOTOS", "1"))
    API_CLOSE_REQUIRES_CHECKLIST = os.getenv("API_CLOSE_REQUIRES_CHECKLIST", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    TELEGRAM_ADMIN_IDS = os.getenv("TELEGRAM_ADMIN_IDS", "")
    BASE_DIR = os.getenv("BASE_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    MEDIA_DIR = os.path.join(BASE_DIR, "media")
    LOG_FILE = os.path.join(BASE_DIR, "logs", "bot.log")
    YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "your-yandex-api-key-here")
    DATABASE_URL = SQLALCHEMY_DATABASE_URI  # Алиас для совместимости
