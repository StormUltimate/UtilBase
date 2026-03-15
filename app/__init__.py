# Path: app/__init__.py
from flask import Flask, redirect, url_for, flash, request, render_template
from app.config import Config
from app.extensions import db, login_manager, migrate
from app.utils.logger import setup_logger
from werkzeug.security import generate_password_hash
from app.models.all_models import Users, Request, RegulationsLink, Client, Contract, Equipment
from datetime import date
from sqlalchemy.exc import SQLAlchemyError, OperationalError, ProgrammingError
from flask_login import login_required

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['UPLOAD_FOLDER'] = 'static/uploads/regulations'

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    migrate.init_app(app, db)

    @login_manager.user_loader
    def load_user(user_id):
        return Users.query.get(int(user_id))

    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True

    logger = setup_logger()
    app.logger = logger

    from app.blueprints.auth import auth_bp
    from app.blueprints.users import users_bp
    from app.blueprints.clients import clients_bp
    from app.blueprints.photos.routes import photos_bp
    from app.blueprints.equipment import equipment_bp
    from app.blueprints.requests.routes import requests_bp
    from app.blueprints.map import map_bp
    from app.blueprints.workers.routes import workers_bp
    from app.blueprints.regulations.routes import regulations_bp
    from app.blueprints.demo import demo_bp
    from app.blueprints.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(clients_bp)
    app.register_blueprint(photos_bp)
    app.register_blueprint(equipment_bp, url_prefix='/equipment')
    app.register_blueprint(requests_bp, url_prefix='/requests')
    app.register_blueprint(map_bp)
    app.register_blueprint(workers_bp, url_prefix='/workers')
    app.register_blueprint(regulations_bp, url_prefix='/regulations')
    app.register_blueprint(demo_bp, url_prefix='/demo')
    app.register_blueprint(admin_bp)

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    @app.route('/demo')
    def demo():
        from app.utils.demo_data import get_demo_data
        return render_template('demo.html', **get_demo_data())

    @app.route('/search', methods=['GET'])
    @login_required
    def search():
        q = (request.args.get('q') or '').strip()
        results = {'clients': [], 'contracts': [], 'equipment': [], 'requests': []}
        if q:
            term = f'%{q}%'
            results['clients'] = Client.query.filter(
                db.or_(
                    Client.full_name.ilike(term),
                    Client.address.ilike(term),
                    Client.phone.ilike(term),
                    Client.email.ilike(term)
                )
            ).limit(20).all()
            results['contracts'] = Contract.query.join(Client).filter(
                db.or_(
                    Client.full_name.ilike(term),
                    Contract.contract_type.ilike(term)
                )
            ).limit(20).all()
            results['equipment'] = Equipment.query.outerjoin(Client).filter(
                db.or_(
                    Equipment.brand.ilike(term),
                    Equipment.model.ilike(term),
                    Equipment.serial_number.ilike(term),
                    Equipment.type.ilike(term),
                    Client.full_name.ilike(term)
                )
            ).limit(20).all()
            results['requests'] = Request.query.outerjoin(Client).filter(
                db.or_(
                    Request.description.ilike(term),
                    Request.request_number.ilike(term),
                    Request.full_name.ilike(term),
                    Client.full_name.ilike(term)
                )
            ).limit(20).all()
        return render_template('search.html', q=q, results=results)

    @app.route('/favicon.ico')
    def favicon():
        return redirect(url_for('static', filename='favicon.ico'))

    @app.errorhandler(404)
    def not_found_error(error):
        return {"error": "Resource not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        return {"error": "Internal server error"}, 500

    def _db_error_response(msg_detail, hint):
        try:
            db.session.rollback()
        except Exception:
            pass
        return f"<h2>Ошибка базы данных</h2><p>{msg_detail}</p><p>{hint}</p>", 503

    @app.errorhandler(OperationalError)
    def db_connection_error(error):
        return _db_error_response(
            "Проверьте: PostgreSQL запущен, в .env указаны правильные "
            "SQLALCHEMY_DATABASE_URI, база создана (например: createdb utilbase).",
            "После настройки выполните: flask db upgrade",
        )

    @app.errorhandler(ProgrammingError)
    def db_table_error(error):
        return _db_error_response(
            "Таблицы не созданы (отношение не существует).",
            "Выполните в каталоге проекта: flask db upgrade",
        )

    @app.before_request
    def before_request():
        if request.blueprint == 'requests':
            try:
                overdue_requests = Request.query.filter(
                    Request.planned_date < date.today(),
                    Request.status.notin_(['closed', 'overdue'])
                ).all()
                for req in overdue_requests:
                    req.status = 'overdue'
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f'Ошибка: {str(e)}', 'danger')

    with app.app_context():
        try:
            if Users.query.filter_by(username='admin').first() is None:
                admin_user = Users(
                    username='admin',
                    password_hash=generate_password_hash('admin', method='pbkdf2:sha256'),
                    role='admin',
                )
                db.session.add(admin_user)
                db.session.commit()
        except (OperationalError, ProgrammingError):
            import warnings
            warnings.warn(
                "БД недоступна или таблицы не созданы. Проверьте .env и PostgreSQL, "
                "затем выполните: flask db upgrade"
            )

    return app