# V:\UtilBase\app\utils\__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.config import Config
from app.utils.logger import setup_logger

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Инициализация базы данных
    db.init_app(app)

    # Настройка логирования
    setup_logger()

    # Регистрация маршрутов
    from app.pages.clients_list import bp as clients_list_bp
    from app.pages.clients_add import bp as clients_add_bp
    from app.pages.clients_delete import bp as clients_delete_bp
    from app.pages.clients_analytics import bp as clients_analytics_bp
    from app.pages.requests_create import bp as requests_create_bp
    from app.pages.requests_today import bp as requests_today_bp
    from app.pages.requests_planned import bp as requests_planned_bp
    from app.pages.requests_overdue import bp as requests_overdue_bp
    from app.pages.requests_work import bp as requests_work_bp
    from app.pages.equipment_list import bp as equipment_list_bp
    from app.pages.equipment_add import bp as equipment_add_bp
    from app.pages.equipment_analytics import bp as equipment_analytics_bp
    from app.pages.contracts_list import bp as contracts_list_bp
    from app.pages.contracts_add import bp as contracts_add_bp
    from app.pages.contracts_analytics import bp as contracts_analytics_bp
    from app.pages.system_settings import bp as system_settings_bp
    from app.pages.system_logs import bp as system_logs_bp

    app.register_blueprint(clients_list_bp)
    app.register_blueprint(clients_add_bp)
    app.register_blueprint(clients_delete_bp)
    app.register_blueprint(clients_analytics_bp)
    app.register_blueprint(requests_create_bp)
    app.register_blueprint(requests_today_bp)
    app.register_blueprint(requests_planned_bp)
    app.register_blueprint(requests_overdue_bp)
    app.register_blueprint(requests_work_bp)
    app.register_blueprint(equipment_list_bp)
    app.register_blueprint(equipment_add_bp)
    app.register_blueprint(equipment_analytics_bp)
    app.register_blueprint(contracts_list_bp)
    app.register_blueprint(contracts_add_bp)
    app.register_blueprint(contracts_analytics_bp)
    app.register_blueprint(system_settings_bp)
    app.register_blueprint(system_logs_bp)

    return app