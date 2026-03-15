from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from werkzeug.utils import secure_filename
import os
from app.models.all_models import RegulationsLink
from app.extensions import db
import spacy  # Для NLP с spaCy (установите spacy и скачайте модель: python -m spacy download ru_core_news_sm)

regulations_bp = Blueprint('regulations', __name__, template_folder='templates')

nlp = spacy.load("ru_core_news_sm")  # Русская модель для NLP

@regulations_bp.route('/', methods=['GET', 'POST'])
@login_required  # Доступ для всех авторизованных
def index():
    upload_folder = os.path.join(regulations_bp.root_path, '../../../static/uploads/regulations')
    os.makedirs(upload_folder, exist_ok=True)

    # Загрузка файла
    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(upload_folder, filename))
            flash('Файл загружен', 'success')

    # Добавление ссылки
    if request.method == 'POST' and 'add_link' in request.form:
        name = request.form['name']
        url = request.form['url']
        if name and url:
            new_link = RegulationsLink(name=name, url=url)
            db.session.add(new_link)
            db.session.commit()
            flash('Ссылка добавлена', 'success')

    # Редактирование ссылки
    if request.method == 'POST' and 'edit_link' in request.form:
        link_id = request.form['link_id']
        name = request.form['name']
        url = request.form['url']
        link = RegulationsLink.query.get(link_id)
        if link:
            link.name = name
            link.url = url
            db.session.commit()
            flash('Ссылка обновлена', 'success')

    # Удаление ссылки
    if request.method == 'POST' and 'delete_link' in request.form:
        link_id = request.form['link_id']
        link = RegulationsLink.query.get(link_id)
        if link:
            db.session.delete(link)
            db.session.commit()
            flash('Ссылка удалена', 'success')

    # NLP поиск (spaCy для извлечения сущностей из запроса)
    nlp_result = None
    if request.method == 'POST' and 'query' in request.form:
        query = request.form['query']
        doc = nlp(query)
        entities = [ent.text for ent in doc.ents]
        nlp_result = f"Извлеченные сущности: {', '.join(entities)} (используйте для поиска в файлах/ссылках)"

    # Список файлов
    files = os.listdir(upload_folder) if os.path.exists(upload_folder) else []

    # Список ссылок из БД
    links = RegulationsLink.query.all()

    # ------------ Фильтры по оборудованию и поиску ------------
    equipment_types = [
        ('all', 'Все типы'),
        ('котел', 'Котлы'),
        ('насос', 'Насосы'),
        ('электрика', 'Электрика'),
        ('бассейн', 'Бассейны'),
        ('вентиляция', 'Вентиляция'),
        ('прочее', 'Прочее'),
    ]

    eq_type = request.args.get('equipment_type', 'all').lower()
    name_q = request.args.get('name', '').strip().lower()
    brand_q = request.args.get('brand', '').strip().lower()
    model_q = request.args.get('model', '').strip().lower()
    power_q = request.args.get('power', '').strip().lower()
    volume_q = request.args.get('volume', '').strip().lower()

    def matches_text(text: str) -> bool:
        t = (text or '').lower()
        if eq_type and eq_type != 'all':
            # Пытаемся найти упоминание типа в имени/пути
            if eq_type not in t:
                # Для "прочее" допускаем всё, что не попало выше
                if eq_type == 'прочее':
                    pass
                else:
                    return False
        if name_q and name_q not in t:
            return False
        if brand_q and brand_q not in t:
            return False
        if model_q and model_q not in t:
            return False
        if power_q and power_q not in t:
            return False
        if volume_q and volume_q not in t:
            return False
        return True

    # Фильтрация файлов по имени
    filtered_files = [f for f in files if matches_text(f)]

    # Фильтрация ссылок по названию и URL
    filtered_links = [ln for ln in links if matches_text(f"{ln.name} {ln.url}")]

    return render_template(
        'regulations/regulations.html',
        files=filtered_files,
        links=filtered_links,
        nlp_result=nlp_result,
        equipment_types=equipment_types,
        current_type=eq_type,
        name_q=name_q,
        brand_q=brand_q,
        model_q=model_q,
        power_q=power_q,
        volume_q=volume_q,
    )

@regulations_bp.route('/delete_file/<filename>', methods=['POST'])
@login_required
def delete_file(filename):
    upload_folder = os.path.join(regulations_bp.root_path, '../../../static/uploads/regulations')
    file_path = os.path.join(upload_folder, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash('Файл удален', 'success')
    else:
        flash('Файл не найден', 'danger')
    return redirect(url_for('regulations.index'))