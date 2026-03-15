# Path: app/blueprints/photos/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required
from app.extensions import db
from app.models.all_models import Media, Client, Request, Equipment, Worker, SystemLogs, TelegramBotUsers, Users
from werkzeug.utils import secure_filename
import os
import json
import shutil
from datetime import datetime
import logging
import re
from PIL import Image
from sqlalchemy import or_, func

photos_bp = Blueprint('photos', __name__, url_prefix='/photos')

logger = logging.getLogger(__name__)

@photos_bp.route('/', methods=['GET'])
@login_required
def photos_list():
    source = request.args.get('source', 'all')
    search_client = request.args.get('client', '')
    search_date = request.args.get('date', '')
    search_author = request.args.get('author', '')
    search_uploader = request.args.get('uploader', '')
    search_description = request.args.get('description', '')
    sort_by = request.args.get('sort_by', 'upload_date')
    sort_order = request.args.get('sort_order', 'desc')
    items_per_row = request.args.get('per_row', '4')
    search_request = request.args.get('request', '')

    try:
        query = db.session.query(
            Media.id,
            Media.file_path,
            Media.upload_date,
            Media.file_type,
            Client.full_name.label('client_name'),
            Client.address.label('client_address'),
            Request.request_number,
            Equipment.serial_number,
            Media.request_id,
            Media.client_id,
            Media.equipment_id,
            Media.author_name,
            Media.description,
            Media.equipment_type
        ).outerjoin(Client, Media.client_id == Client.id
        ).outerjoin(Request, Media.request_id == Request.id
        ).outerjoin(Equipment, Media.equipment_id == Equipment.id
        ).outerjoin(Users, Media.created_by_user_id == Users.id
        ).filter(Media.file_type.in_(['photo', 'video', 'document']))

        if source == 'bot':
            query = query.filter(Media.chat_id.isnot(None))
        elif source == 'app':
            query = query.filter(Media.chat_id.is_(None))

        if search_client:
            query = query.filter(
                or_(
                    Client.full_name.ilike(f'%{search_client}%'),
                    Client.address.ilike(f'%{search_client}%'),
                    Client.phone.ilike(f'%{search_client}%')
                )
            )
        if search_date:
            try:
                search_date = datetime.strptime(search_date, '%Y-%m-%d')
                query = query.filter(func.date(Media.upload_date) == search_date)
            except ValueError:
                logger.error(f"Неверный формат даты: {search_date}")
        if search_author:
            query = query.filter(Media.author_name.ilike(f'%{search_author}%'))
        if search_uploader:
            query = query.filter(Users.username.ilike(f'%{search_uploader}%'))
        if search_description:
            query = query.filter(Media.description.ilike(f'%{search_description}%'))
        if search_request:
            query = query.filter(Request.request_number.ilike(f'%{search_request}%'))

        if sort_by == 'client_name':
            query = query.order_by(Client.full_name.asc() if sort_order == 'asc' else Client.full_name.desc())
        elif sort_by == 'id':
            query = query.order_by(Media.id.asc() if sort_order == 'asc' else Media.id.desc())
        elif sort_by == 'author_name':
            query = query.order_by(Media.author_name.asc() if sort_order == 'asc' else Media.author_name.desc())
        elif sort_by == 'uploader':
            query = query.order_by(Users.username.asc() if sort_order == 'asc' else Users.username.desc())
        elif sort_by == 'description':
            query = query.order_by(Media.description.asc() if sort_order == 'asc' else Media.description.desc())
        else:
            query = query.order_by(Media.upload_date.asc() if sort_order == 'asc' else Media.upload_date.desc())

        photos = query.all()

        clients = db.session.query(Client.id, Client.full_name).order_by(Client.full_name).all()
        requests = db.session.query(Request.id, Request.request_number).order_by(Request.request_number).all()
        equipment = db.session.query(Equipment.id, Equipment.serial_number).order_by(Equipment.serial_number).all()
        workers = db.session.query(Worker.id, Worker.full_name).order_by(Worker.full_name).all()
        users = Users.query.order_by(Users.username).all()

        logger.info(f"Успешно загружен список медиа (source={source}, count={len(photos)})")
        db.session.add(SystemLogs(
            created_at=datetime.now(),
            level='INFO',
            message=f'Загружен список медиа (source={source}, count={len(photos)})'
        ))
        db.session.commit()

        return render_template(
            'photos/photos.html',
            photos=photos,
            search_client=search_client,
            search_date=search_date,
            search_author=search_author,
            search_uploader=search_uploader,
            search_description=search_description,
            search_request=search_request,
            sort_by=sort_by,
            sort_order=sort_order,
            items_per_row=items_per_row,
            clients=clients,
            requests=requests,
            equipment=equipment,
            workers=workers,
            users=users,
            source=source
        )
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'error')
        logger.error(f"Ошибка при загрузке списка медиа: {str(e)}")
        db.session.add(SystemLogs(
            created_at=datetime.now(),
            level='ERROR',
            message=f'Ошибка при загрузке списка медиа: {str(e)}'
        ))
        db.session.commit()
        return render_template(
            'photos/photos.html',
            photos=[],
            search_client=search_client,
            search_date=search_date,
            search_author=search_author,
            search_uploader=search_uploader,
            search_description=search_description,
            search_request=search_request,
            sort_by=sort_by,
            sort_order=sort_order,
            items_per_row=items_per_row,
            clients=[],
            requests=[],
            equipment=[],
            workers=[],
            users=[],
            source=source
        )

@photos_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_photo():
    try:
        clients = db.session.query(Client.id, Client.full_name).order_by(Client.full_name).all()

        if request.method == 'POST':
            if 'file' not in request.files:
                flash('Файл не выбран', 'error')
                logger.warning("Попытка загрузки медиа без выбора файла")
                return redirect(url_for('photos.upload_photo'))

            files = request.files.getlist('file')
            if not files or (len(files) == 1 and files[0].filename == ''):
                flash('Файл не выбран', 'error')
                logger.warning("Попытка загрузки медиа с пустым именем файла")
                return redirect(url_for('photos.upload_photo'))

            client_id = request.form.get('client_id')
            file_type = request.form.get('file_type', 'photo')
            upload_folder = os.path.join(current_app.root_path, f"static/uploads/{file_type}s")
            os.makedirs(upload_folder, exist_ok=True)
            count = 0
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    if filename:
                        file_path = os.path.join(upload_folder, filename)
                        file.save(file_path)
                        media = Media(
                            file_path=f'uploads/{file_type}s/{filename}',
                            upload_date=datetime.now(),
                            client_id=client_id or None,
                            file_type=file_type
                        )
                        db.session.add(media)
                        count += 1
            if count > 0:
                db.session.commit()
                flash(f'Загружено файлов: {count}', 'success')
                logger.info(f"Успешно загружено {count} {file_type}(s), client_id={client_id}")
                db.session.add(SystemLogs(
                    created_at=datetime.now(),
                    level='INFO',
                    message=f'Загружено {count} {file_type}(s), client_id={client_id}'
                ))
                db.session.commit()
            next_url = request.args.get('next') or request.form.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('photos.photos_list'))

        return render_template('photos/upload.html', clients=clients)
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'error')
        logger.error(f"Ошибка при загрузке {file_type} {filename if 'filename' in locals() else ''}: {str(e)}")
        db.session.add(SystemLogs(
            created_at=datetime.now(),
            level='ERROR',
            message=f'Ошибка при загрузке {file_type} {filename if "filename" in locals() else ""}: {str(e)}'
        ))
        db.session.commit()
        return render_template('photos/upload.html', clients=[])

@photos_bp.route('/import_chat', methods=['GET', 'POST'])
@login_required
def import_chat():
    if request.method == 'POST':
        logger.info("Получен POST-запрос на импорт чата")

        if 'json_file' not in request.files:
            flash('JSON-файл не выбран', 'error')
            logger.warning("Попытка импорта чата без выбора JSON-файла")
            return redirect(url_for('photos.import_chat'))

        json_file = request.files['json_file']
        if json_file.filename == '':
            flash('JSON-файл не выбран', 'error')
            logger.warning("Попытка импорта чата с пустым именем JSON-файла")
            return redirect(url_for('photos.import_chat'))

        if not json_file.filename.endswith('.json'):
            flash('Файл должен быть в формате JSON', 'error')
            logger.warning(f"Попытка импорта чата с неподдерживаемым форматом: {json_file.filename}")
            return redirect(url_for('photos.import_chat'))

        media_path = request.form.get('media_path')
        logger.info(f"Указанный путь к медиафайлам: {media_path}")
        if not media_path or not os.path.exists(media_path):
            flash('Указанный путь к папке с медиафайлами не существует', 'error')
            logger.warning(f"Указанный путь к медиафайлам не существует: {media_path}")
            return redirect(url_for('photos.import_chat'))

        try:
            chat_data = json.load(json_file)
            logger.info(f"JSON-файл успешно прочитан: {json_file.filename}")

            imported_media = 0
            for message in chat_data.get('messages', []):
                if message.get('type') != 'message':
                    continue

                author_name = message.get('from')
                author_id = None
                if message.get('from_id'):
                    telegram_id = message['from_id'].replace('user', '').replace('channel', '')
                    tg_user = TelegramBotUsers.query.filter_by(telegram_id=telegram_id).first()
                    if tg_user:
                        author_id = tg_user.user_id

                message_date = datetime.strptime(message.get('date'), '%Y-%m-%dT%H:%M:%S')
                description = message.get('text', '') if isinstance(message.get('text'), str) else ''
                file_path = message.get('photo') or message.get('file')
                file_type = None
                content_type = message.get('mime_type')
                file_size = message.get('photo_file_size') or message.get('file_size')
                width = message.get('width')
                height = message.get('height')

                if file_path and file_path != '(File not included. Change data exporting settings to download.)':
                    logger.debug(f"Обрабатывается файл: {file_path}")
                    if file_path.startswith('photos/'):
                        file_type = 'photo'
                        target_dir = 'static/uploads/photos'
                        db_file_path = f'uploads/photos/{os.path.basename(file_path)}'
                    elif content_type == 'video/mp4':
                        file_type = 'video'
                        target_dir = 'static/uploads/videos'
                        db_file_path = f'uploads/videos/{os.path.basename(file_path)}'
                    else:
                        file_type = 'document'
                        target_dir = 'static/uploads/documents'
                        db_file_path = f'uploads/documents/{os.path.basename(file_path)}'

                    source_file = os.path.join(media_path, os.path.basename(file_path))
                    target_file_dir = os.path.join(current_app.root_path, target_dir)
                    os.makedirs(target_file_dir, exist_ok=True)
                    target_file = os.path.join(target_file_dir, os.path.basename(file_path))
                    if not os.path.exists(source_file):
                        logger.warning(f"Файл не найден в папке экспорта: {source_file}")
                        continue

                    shutil.copy2(source_file, target_file)
                    logger.debug(f"Скопирован файл: {source_file} -> {target_file}")

                    if Media.query.filter_by(file_path=db_file_path).first():
                        logger.debug(f"Файл уже существует в базе, пропускаем: {db_file_path}")
                        continue

                    request_id = None
                    if description:
                        match = re.search(r'#заявка(\d+)', description)
                        if match:
                            request_number = match.group(1)
                            req = Request.query.filter_by(request_number=request_number).first()
                            if req:
                                request_id = req.id

                    if file_type == 'photo' and (not width or not height):
                        try:
                            with Image.open(target_file) as img:
                                width, height = img.size
                        except Exception as e:
                            logger.warning(f"Не удалось получить размеры изображения {target_file}: {str(e)}")

                    media = Media(
                        file_path=db_file_path,
                        file_type=file_type,
                        upload_date=message_date,
                        description=description,
                        created_by_user_id=author_id,
                        author_name=author_name,
                        category='work',
                        width=width,
                        height=height,
                        file_size=file_size,
                        content_type=content_type,
                        request_id=request_id
                    )
                    db.session.add(media)
                    imported_media += 1

            db.session.add(SystemLogs(
                created_at=datetime.now(),
                level='INFO',
                message=f'Чат импортирован, добавлено {imported_media} медиа'
            ))
            db.session.commit()
            flash(f'Чат успешно импортирован! Добавлено {imported_media} медиа.', 'success')
            logger.info(f"Чат импортирован, добавлено {imported_media} медиа")
            return redirect(url_for('photos.photos_list'))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при импорте чата: {str(e)}', 'error')
            logger.error(f"Ошибка при импорте чата: {str(e)}")
            db.session.add(SystemLogs(
                created_at=datetime.now(),
                level='ERROR',
                message=f'Ошибка при импорте чата: {str(e)}'
            ))
            db.session.commit()
            return redirect(url_for('photos.import_chat'))

    return render_template('photos/import_chat.html')

@photos_bp.route('/edit/<int:photo_id>', methods=['GET', 'POST'])
@login_required
def edit_photo(photo_id):
    try:
        if request.method == 'POST':
            client_id = request.form.get('client_id')
            request_id = request.form.get('request_id')
            equipment_id = request.form.get('equipment_id')
            description = request.form.get('description')
            equipment_type = request.form.get('equipment_type')

            media = db.session.query(Media).filter_by(id=photo_id).first()
            if not media:
                flash('Медиа не найдено', 'error')
                logger.warning(f"Медиа ID={photo_id} не найдено")
                db.session.add(SystemLogs(
                    created_at=datetime.now(),
                    level='WARNING',
                    message=f'Медиа ID={photo_id} не найдено'
                ))
                db.session.commit()
                return redirect(url_for('photos.photos_list'))

            media.client_id = client_id or None
            media.request_id = request_id or None
            media.equipment_id = equipment_id or None
            media.description = description or None
            media.equipment_type = equipment_type or None
            db.session.commit()

            flash('Медиа успешно обновлено', 'success')
            logger.info(f"Успешно обновлено медиа ID={photo_id}, client_id={client_id}, description={description}, equipment_type={equipment_type}")
            db.session.add(SystemLogs(
                created_at=datetime.now(),
                level='INFO',
                message=f'Обновлено медиа ID={photo_id}, client_id={client_id}, description={description}, equipment_type={equipment_type}'
            ))
            db.session.commit()
            return redirect(url_for('photos.photos_list'))

        media = db.session.query(Media).filter_by(id=photo_id).first()
        if not media:
            flash('Медиа не найдено', 'error')
            logger.warning(f"Медиа ID={photo_id} не найдено")
            db.session.add(SystemLogs(
                created_at=datetime.now(),
                level='WARNING',
                message=f'Медиа ID={photo_id} не найдено'
            ))
            db.session.commit()
            return redirect(url_for('photos.photos_list'))

        clients = db.session.query(Client.id, Client.full_name).order_by(Client.full_name).all()
        requests = db.session.query(Request.id, Request.request_number).order_by(Request.request_number).all()
        equipment = db.session.query(Equipment.id, Equipment.serial_number).order_by(Equipment.serial_number).all()

        return render_template('photos/edit.html', photo=media, clients=clients, requests=requests, equipment=equipment)
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'error')
        logger.error(f"Ошибка при редактировании медиа ID={photo_id}: {str(e)}")
        db.session.add(SystemLogs(
            created_at=datetime.now(),
            level='ERROR',
            message=f'Ошибка при редактировании медиа ID={photo_id}: {str(e)}'
        ))
        db.session.commit()
        return redirect(url_for('photos.photos_list'))

@photos_bp.route('/delete', methods=['POST'])
@login_required
def delete_photos():
    photo_ids = request.form.getlist('photo_ids')
    if not photo_ids:
        flash('Файлы не выбраны', 'error')
        logger.warning("Попытка удаления медиа без выбора файлов")
        db.session.add(SystemLogs(
            created_at=datetime.now(),
            level='WARNING',
            message='Попытка удаления медиа без выбора файлов'
        ))
        db.session.commit()
        return redirect(url_for('photos.photos_list'))

    try:
        photo_ids = [int(pid) for pid in photo_ids]
    except ValueError:
        flash('Некорректные ID медиа', 'error')
        logger.error(f"Некорректные ID медиа для удаления: {photo_ids}")
        return redirect(url_for('photos.photos_list'))

    try:
        media_records = db.session.query(Media).filter(Media.id.in_(photo_ids)).all()
        file_paths = [media.file_path for media in media_records]

        db.session.query(Media).filter(Media.id.in_(photo_ids)).delete(synchronize_session=False)
        db.session.commit()
        deleted_count = len(media_records)

        deleted_files = []
        for file_path in file_paths:
            full_path = os.path.join(current_app.root_path, 'static', file_path.replace('/', os.sep))
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    deleted_files.append(full_path)
                except Exception as e:
                    logger.error(f"Ошибка при удалении файла {full_path}: {str(e)}")
            else:
                logger.warning(f"Файл не найден: {full_path}")

        flash(f'Файлы успешно удалены: {deleted_count}', 'success')
        logger.info(f"Успешно удалены медиа: {photo_ids}, файлы: {deleted_files}")
        db.session.add(SystemLogs(
            created_at=datetime.now(),
            level='INFO',
            message=f'Удалены медиа: {photo_ids}, файлы: {deleted_files}'
        ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'error')
        logger.error(f"Ошибка при удалении медиа {photo_ids}: {str(e)}")
        db.session.add(SystemLogs(
            created_at=datetime.now(),
            level='ERROR',
            message=f'Ошибка при удалении медиа {photo_ids}: {str(e)}'
        ))
        db.session.commit()
        return redirect(url_for('photos.photos_list'))

    return redirect(url_for('photos.photos_list'))

@photos_bp.route('/attach_to_request', methods=['POST'])
@login_required
def attach_to_request():
    photo_ids = request.form.getlist('photo_ids')
    request_id = request.form.get('request_id')

    if not photo_ids:
        flash('Файлы не выбраны', 'error')
        logger.warning("Попытка привязки медиа без выбора файлов")
        return redirect(url_for('photos.photos_list'))

    if not request_id:
        flash('Заявка не выбрана', 'error')
        logger.warning("Попытка привязки медиа без выбора заявки")
        return redirect(url_for('photos.photos_list'))

    try:
        photo_ids = [int(pid) for pid in photo_ids]
        request_id = int(request_id)
    except ValueError:
        flash('Некорректные ID медиа или заявки', 'error')
        logger.error(f"Некорректные ID медиа или заявки: photo_ids={photo_ids}, request_id={request_id}")
        return redirect(url_for('photos.photos_list'))

    try:
        request = db.session.query(Request).filter_by(id=request_id).first()
        if not request:
            flash('Заявка не найдена', 'error')
            logger.warning(f"Заявка ID={request_id} не найдена")
            return redirect(url_for('photos.photos_list'))

        updated = db.session.query(Media).filter(Media.id.in_(photo_ids)).update(
            {Media.request_id: request_id}, synchronize_session=False
        )
        db.session.commit()

        flash(f'Медиа успешно привязаны к заявке: {updated}', 'success')
        logger.info(f"Медиа привязаны к заявке ID={request_id}: {photo_ids}")
        db.session.add(SystemLogs(
            created_at=datetime.now(),
            level='INFO',
            message=f'Медиа привязаны к заявке ID={request_id}: {photo_ids}'
        ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'error')
        logger.error(f"Ошибка при привязке медиа к заявке ID={request_id}: {str(e)}")
        db.session.add(SystemLogs(
            created_at=datetime.now(),
            level='ERROR',
            message=f'Ошибка при привязке медиа к заявке ID={request_id}: {str(e)}'
        ))
        db.session.commit()
        return redirect(url_for('photos.photos_list'))

    return redirect(url_for('photos.photos_list'))

@photos_bp.route('/view/<int:id>')
@login_required
def view(id):
    try:
        media = db.session.query(Media).get_or_404(id)
        directory = os.path.dirname(media.file_path)
        filename = os.path.basename(media.file_path)
        full_dir = os.path.join('static', directory)
        if not os.path.exists(os.path.join(current_app.root_path, full_dir, filename)):
            logger.warning(f"Файл не найден: {media.file_path}")
            flash('Файл не найден', 'error')
            return redirect(url_for('photos.photos_list'))
        return send_from_directory(full_dir, filename)
    except Exception as e:
        logger.error(f"Ошибка в view медиа ID={id}: {str(e)}")
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('photos.photos_list'))