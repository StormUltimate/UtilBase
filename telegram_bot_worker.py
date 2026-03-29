#!/usr/bin/env python3
# Path: telegram_bot_worker.py — отдельный процесс polling Telegram (вызывается из веб-интерфейса).
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from app import create_app
from app.telegram.bot_service import run_telegram_bot

app = create_app()
with app.app_context():
    run_telegram_bot(app)
