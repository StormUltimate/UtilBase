# Path: app/config.py
import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key')
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:asdf1234@localhost:5432/utilbase'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-jwt-secret-key')
    JWT_TOKEN_LOCATION = ['headers']
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    BOT_TOKEN = os.getenv("BOT_TOKEN", "0000000000000000000000000000000")
    BASE_DIR = os.getenv("BASE_DIR", "V:\\UtilBase")
    MEDIA_DIR = os.path.join(BASE_DIR, "media")
    LOG_FILE = os.path.join(BASE_DIR, "logs", "bot.log")
    YANDEX_API_KEY = os.getenv('YANDEX_API_KEY', 'your-yandex-api-key-here')
    DATABASE_URL = SQLALCHEMY_DATABASE_URI  # Алиас для совместимости