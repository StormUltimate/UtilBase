# Path: app/blueprints/photos/routes.py
import json
import logging
import os
import re
import shutil
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from PIL import Image
from sqlalchemy import Date as SaDate
from sqlalchemy import cast, false, func, nullslast, or_
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.all_models import (
    Client,
    Equipment,
    Media,
    Request,
    SystemLogs,
    TelegramBotUsers,
    Users,
    Worker,
)
from app.utils.import_fs_browser import browse_directory
from app.utils.telegram_export import telegram_export_text_to_plain

photos_bp = Blueprint("photos", __name__, url_prefix="/photos")

logger = logging.getLogger(__name__)


def _absolute_media_disk_path(file_path: str) -> str:
    """
    Абсолютный путь к файлу медиа на диске.
    - Загрузки из мобильного API v1: file_path вида requests/<id>/... → каталог MEDIA_DIR.
    - Остальное (uploads/...): как раньше, под app/static/.
    """
    if not file_path:
        return ""
    norm = file_path.replace("\\", "/").lstrip("/")
    if norm.startswith("requests/"):
        base = current_app.config.get("MEDIA_DIR") or os.path.join(
            current_app.config.get("BASE_DIR") or current_app.root_path,
            "media",
        )
        return os.path.normpath(os.path.join(base, norm))
    return os.path.normpath(
        os.path.join(current_app.root_path, "static", norm.replace("/", os.sep))
    )


def _safe_relative_next():
    """Валидированный относительный next (без open-redirect) или None."""
    if request.method == "POST":
        raw = (request.form.get("next") or request.args.get("next") or "").strip()
    else:
        raw = (request.args.get("next") or "").strip()
    if raw and raw.startswith("/"):
        parsed = urlparse(raw)
        if not parsed.scheme and not parsed.netloc:
            return raw
    return None


def _int_or_none(val):
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# Сетка превью: только 6 в ряд (см. шаблон). Пагинация — чтобы не отдавать десятки тысяч <img> за раз.
PHOTOS_GRID_COLS = 6
PHOTOS_PER_PAGE = 48


def _parse_telegram_export_date(s):
    if s is None:
        raise ValueError("пустая дата")
    raw = str(s).strip()
    if not raw:
        raise ValueError("пустая дата")
    if len(raw) >= 20 and raw[19] == "Z" and "T" in raw:
        raw = raw[:19]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError:
        pass
    raise ValueError(f"неизвестный формат даты: {raw[:60]}")


def _resolve_export_media_file(media_path, rel_path):
    """Путь к файлу в экспорте: учитывает подпапки photos/, video_files/ и т.д."""
    rel = (rel_path or "").strip()
    if not rel or rel.startswith("("):
        return None
    rel_norm = rel.replace("/", os.sep)
    base = os.path.basename(rel_norm)
    candidates = [
        os.path.normpath(os.path.join(media_path, rel_norm)),
        os.path.normpath(os.path.join(media_path, base)),
        os.path.normpath(os.path.join(media_path, "photos", base)),
        os.path.normpath(os.path.join(media_path, "video_files", base)),
        os.path.normpath(os.path.join(media_path, "files", base)),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _expand_caption_neighbor_ids(anchor_ids, neighbor_span, neighbor_minutes, source):
    """Добавляет к якорям медиа: ±neighbor_span по telegram_message_id или ±минутам.

    Ограничения, чтобы не смешивать разных людей в одном чате:
    - тот же календарный день, что у якоря;
    - тот же author_name, что у якоря (без автора соседей не расширяем)."""
    if not anchor_ids:
        return set()
    neighbor_span = max(1, min(int(neighbor_span or 20), 500))
    neighbor_minutes = max(1, min(int(neighbor_minutes or 10), 1440))
    anchors = Media.query.filter(Media.id.in_(anchor_ids)).all()
    out = set(anchor_ids)
    for m in anchors:
        auth = (m.author_name or "").strip()
        if not auth:
            continue

        if m.chat_id and m.telegram_message_id is not None:
            if not m.upload_date:
                continue
            day = m.upload_date.date()
            lo = m.telegram_message_id - neighbor_span
            hi = m.telegram_message_id + neighbor_span
            q = Media.query.filter(
                Media.chat_id == m.chat_id,
                Media.author_name == auth,
                Media.telegram_message_id.isnot(None),
                Media.telegram_message_id >= lo,
                Media.telegram_message_id <= hi,
                cast(Media.upload_date, SaDate) == day,
                Media.file_type.in_(["photo", "video", "document"]),
            )
            if source == "bot":
                q = q.filter(Media.chat_id.isnot(None))
            elif source == "app":
                q = q.filter(Media.chat_id.is_(None))
            out.update(r[0] for r in q.with_entities(Media.id).all())
        elif m.upload_date:
            day = m.upload_date.date()
            t0 = m.upload_date - timedelta(minutes=neighbor_minutes)
            t1 = m.upload_date + timedelta(minutes=neighbor_minutes)
            q = Media.query.filter(
                Media.upload_date >= t0,
                Media.upload_date <= t1,
                cast(Media.upload_date, SaDate) == day,
                Media.author_name == auth,
                Media.file_type.in_(["photo", "video", "document"]),
            )
            if m.chat_id:
                q = q.filter(Media.chat_id == m.chat_id)
            if source == "bot":
                q = q.filter(Media.chat_id.isnot(None))
            elif source == "app":
                q = q.filter(Media.chat_id.is_(None))
            out.update(r[0] for r in q.with_entities(Media.id).all())
    return out


@photos_bp.route("/", methods=["GET"])
@login_required
def photos_list():
    source = request.args.get("source", "all")
    category = (request.args.get("category") or "").strip()
    search_client = request.args.get("client", "")
    search_date = request.args.get("date", "")
    search_author = request.args.get("author", "")
    search_uploader = request.args.get("uploader", "")
    search_description = (request.args.get("description") or "").strip()
    sort_by = request.args.get("sort_by", "upload_date")
    sort_order = request.args.get("sort_order", "desc")
    items_per_row = str(PHOTOS_GRID_COLS)
    search_request = request.args.get("request", "")
    caption_context = request.args.get("caption_context", "1") == "1"
    try:
        neighbor_span = int(request.args.get("neighbor_span", 20))
    except ValueError:
        neighbor_span = 20
    try:
        neighbor_minutes = int(request.args.get("neighbor_minutes", 10))
    except ValueError:
        neighbor_minutes = 10

    page = request.args.get("page", 1, type=int)
    if page is None or page < 1:
        page = 1

    def _photos_page_url(page_num: int) -> str:
        d = request.args.to_dict(flat=True)
        d["page"] = str(page_num)
        return url_for("photos.photos_list") + "?" + urlencode(d)

    def _with_params(**kwargs) -> str:
        """Ссылка на photos_list с заменой части query-параметров."""
        d = request.args.to_dict(flat=True)
        for k, v in kwargs.items():
            if v is None:
                d.pop(k, None)
            else:
                d[k] = str(v)
        return url_for("photos.photos_list") + ("?" + urlencode(d) if d else "")

    try:
        query = (
            db.session.query(
                Media.id,
                Media.file_path,
                Media.upload_date,
                Media.file_type,
                Client.full_name.label("client_name"),
                Client.address.label("client_address"),
                Request.request_number,
                Equipment.serial_number,
                Media.request_id,
                Media.client_id,
                Media.equipment_id,
                Media.author_name,
                Media.description,
                Media.equipment_type,
            )
            .outerjoin(Client, Media.client_id == Client.id)
            .outerjoin(Request, Media.request_id == Request.id)
            .outerjoin(Equipment, Media.equipment_id == Equipment.id)
            .outerjoin(Users, Media.created_by_user_id == Users.id)
            .filter(Media.file_type.in_(["photo", "video", "document"]))
        )

        if source == "bot":
            query = query.filter(Media.chat_id.isnot(None))
        elif source == "app":
            query = query.filter(Media.chat_id.is_(None))
        if category:
            query = query.filter(Media.category == category)

        if search_client:
            query = query.filter(
                or_(
                    Client.full_name.ilike(f"%{search_client}%"),
                    Client.address.ilike(f"%{search_client}%"),
                    Client.phone.ilike(f"%{search_client}%"),
                )
            )
        if search_date:
            try:
                search_date = datetime.strptime(search_date, "%Y-%m-%d")
                query = query.filter(func.date(Media.upload_date) == search_date)
            except ValueError:
                logger.error(f"Неверный формат даты: {search_date}")
        if search_author:
            query = query.filter(Media.author_name.ilike(f"%{search_author}%"))
        if search_uploader:
            query = query.filter(Users.username.ilike(f"%{search_uploader}%"))
        neighbor_sort = False
        if search_description:
            if caption_context:
                anchor_query = query.filter(Media.description.ilike(f"%{search_description}%"))
                anchor_ids = [row[0] for row in anchor_query.with_entities(Media.id).all()]
                expanded_ids = _expand_caption_neighbor_ids(
                    anchor_ids,
                    neighbor_span,
                    neighbor_minutes,
                    source,
                )
                if not expanded_ids:
                    query = query.filter(false())
                else:
                    query = query.filter(Media.id.in_(expanded_ids))
                neighbor_sort = True
            else:
                query = query.filter(Media.description.ilike(f"%{search_description}%"))
        if search_request:
            query = query.filter(Request.request_number.ilike(f"%{search_request}%"))

        if neighbor_sort:
            query = query.order_by(
                nullslast(Media.chat_id.asc()),
                nullslast(Media.telegram_message_id.asc()),
                Media.upload_date.asc(),
            )
        elif sort_by == "client_name":
            query = query.order_by(
                Client.full_name.asc() if sort_order == "asc" else Client.full_name.desc()
            )
        elif sort_by == "id":
            query = query.order_by(Media.id.asc() if sort_order == "asc" else Media.id.desc())
        elif sort_by == "author_name":
            query = query.order_by(
                Media.author_name.asc() if sort_order == "asc" else Media.author_name.desc()
            )
        elif sort_by == "uploader":
            query = query.order_by(
                Users.username.asc() if sort_order == "asc" else Users.username.desc()
            )
        elif sort_by == "description":
            query = query.order_by(
                Media.description.asc() if sort_order == "asc" else Media.description.desc()
            )
        else:
            query = query.order_by(
                Media.upload_date.asc() if sort_order == "asc" else Media.upload_date.desc()
            )

        total_count = query.count()
        total_pages = (
            max(1, (total_count + PHOTOS_PER_PAGE - 1) // PHOTOS_PER_PAGE) if total_count else 1
        )
        if page > total_pages:
            page = total_pages
        photos = query.offset((page - 1) * PHOTOS_PER_PAGE).limit(PHOTOS_PER_PAGE).all()

        clients = db.session.query(Client.id, Client.full_name).order_by(Client.full_name).all()
        requests = (
            db.session.query(Request.id, Request.request_number)
            .order_by(Request.request_number)
            .all()
        )
        equipment = (
            db.session.query(Equipment.id, Equipment.serial_number)
            .order_by(Equipment.serial_number)
            .all()
        )
        workers = db.session.query(Worker.id, Worker.full_name).order_by(Worker.full_name).all()
        users = Users.query.order_by(Users.username).all()
        author_names = [
            r[0]
            for r in db.session.query(Media.author_name)
            .filter(Media.author_name.isnot(None), Media.author_name != "")
            .distinct()
            .order_by(Media.author_name)
            .all()
        ]

        logger.debug(
            "Список медиа: source=%s page=%s/%s total=%s на странице=%s",
            source,
            page,
            total_pages,
            total_count,
            len(photos),
        )

        return render_template(
            "photos/photos.html",
            photos=photos,
            category=category,
            defects_url=_with_params(category="defect", page=1),
            clear_category_url=_with_params(category=None, page=1),
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
            author_names=author_names,
            source=source,
            caption_context=caption_context,
            neighbor_span=neighbor_span,
            neighbor_minutes=neighbor_minutes,
            page=page,
            total_count=total_count,
            total_pages=total_pages,
            per_page=PHOTOS_PER_PAGE,
            photos_page_url=_photos_page_url,
        )
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка: {str(e)}", "error")
        logger.error(f"Ошибка при загрузке списка медиа: {str(e)}")
        db.session.add(
            SystemLogs(
                created_at=datetime.now(),
                level="ERROR",
                message=f"Ошибка при загрузке списка медиа: {str(e)}",
            )
        )
        db.session.commit()
        return render_template(
            "photos/photos.html",
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
            author_names=[],
            source=source,
            caption_context=caption_context,
            neighbor_span=neighbor_span,
            neighbor_minutes=neighbor_minutes,
            page=page,
            total_count=0,
            total_pages=1,
            per_page=PHOTOS_PER_PAGE,
            photos_page_url=_photos_page_url,
        )


@photos_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload_photo():
    try:
        if request.method == "POST":
            if "file" not in request.files:
                flash("Файл не выбран", "error")
                logger.warning("Попытка загрузки медиа без выбора файла")
                return redirect(url_for("photos.upload_photo"))

            files = request.files.getlist("file")
            if not files or (len(files) == 1 and files[0].filename == ""):
                flash("Файл не выбран", "error")
                logger.warning("Попытка загрузки медиа с пустым именем файла")
                return redirect(url_for("photos.upload_photo"))

            client_id = _int_or_none(request.form.get("client_id"))
            request_id = _int_or_none(request.form.get("request_id"))
            if request_id and not client_id:
                req_row = db.session.get(Request, request_id)
                if req_row and req_row.client_id:
                    client_id = req_row.client_id
            elif request_id and client_id:
                req_row = db.session.get(Request, request_id)
                if req_row and req_row.client_id and req_row.client_id != client_id:
                    flash(
                        "Заявка относится к другому клиенту; привязка к заявке не выполнена.",
                        "warning",
                    )
                    request_id = None
            description = (request.form.get("description") or "").strip() or None
            category = (request.form.get("category") or "").strip() or None
            file_type = request.form.get("file_type", "photo")
            upload_folder = os.path.join(current_app.root_path, f"static/uploads/{file_type}s")
            os.makedirs(upload_folder, exist_ok=True)
            count = 0
            uid = current_user.id if current_user.is_authenticated else None
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    if filename:
                        file_path = os.path.join(upload_folder, filename)
                        file.save(file_path)
                        media = Media(
                            file_path=f"uploads/{file_type}s/{filename}",
                            upload_date=datetime.now(),
                            client_id=client_id,
                            request_id=request_id,
                            file_type=file_type,
                            description=description,
                            category=category,
                            created_by_user_id=uid,
                        )
                        db.session.add(media)
                        count += 1
            if count > 0:
                db.session.commit()
                flash(f"Загружено файлов: {count}", "success")
                logger.info(
                    "Успешно загружено %s %s(s), client_id=%s request_id=%s",
                    count,
                    file_type,
                    client_id,
                    request_id,
                )
                db.session.add(
                    SystemLogs(
                        created_at=datetime.now(),
                        level="INFO",
                        message=f"Загружено {count} {file_type}(s), client_id={client_id}, request_id={request_id}",
                    )
                )
                db.session.commit()
            dest = _safe_relative_next()
            if dest:
                return redirect(dest)
            return redirect(url_for("photos.photos_list"))

        next_url = _safe_relative_next()
        pref_client_id = request.args.get("client_id")
        pref_request_id = request.args.get("request_id")
        pref_client_label = ""
        if pref_client_id:
            try:
                c = db.session.get(Client, int(pref_client_id))
                if c:
                    pref_client_label = f"{c.full_name or '—'} · {c.phone or '—'}"
            except (ValueError, TypeError):
                pass
        return render_template(
            "photos/upload.html",
            next_url=next_url,
            pref_client_id=pref_client_id,
            pref_request_id=pref_request_id,
            pref_client_label=pref_client_label,
        )
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка: {str(e)}", "error")
        logger.error(
            f"Ошибка при загрузке {file_type} {filename if 'filename' in locals() else ''}: {str(e)}"
        )
        db.session.add(
            SystemLogs(
                created_at=datetime.now(),
                level="ERROR",
                message=f"Ошибка при загрузке {file_type} {filename if 'filename' in locals() else ''}: {str(e)}",
            )
        )
        db.session.commit()
        return render_template(
            "photos/upload.html",
            next_url=_safe_relative_next(),
            pref_client_id=request.args.get("client_id"),
            pref_request_id=request.args.get("request_id"),
            pref_client_label="",
        )


@photos_bp.route("/import_chat", methods=["GET", "POST"])
@login_required
def import_chat():
    next_url = _safe_relative_next()
    if request.method == "POST":
        logger.info("Получен POST-запрос на импорт чата")

        media_path = (request.form.get("media_path") or "").strip().strip('"').strip("'")
        media_path = os.path.normpath(media_path) if media_path else ""
        json_path_local = (request.form.get("json_path") or "").strip().strip('"').strip("'")
        json_path_local = os.path.normpath(json_path_local) if json_path_local else ""

        chat_data = None
        json_label = ""

        if json_path_local:
            if not os.path.isfile(json_path_local):
                flash(f"Файл JSON не найден: {json_path_local}", "error")
                logger.warning("import_chat: json_path не файл: %s", json_path_local)
                return redirect(
                    url_for("photos.import_chat", next=next_url)
                    if next_url
                    else url_for("photos.import_chat")
                )
            if not json_path_local.lower().endswith(".json"):
                flash("Путь к JSON должен заканчиваться на .json", "error")
                return redirect(
                    url_for("photos.import_chat", next=next_url)
                    if next_url
                    else url_for("photos.import_chat")
                )
            try:
                with open(json_path_local, encoding="utf-8") as f:
                    chat_data = json.load(f)
                json_label = json_path_local
                logger.info("JSON прочитан с диска: %s", json_path_local)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
                flash(f"Не удалось прочитать JSON с диска: {e}", "error")
                logger.exception("import_chat: ошибка чтения json_path")
                return redirect(
                    url_for("photos.import_chat", next=next_url)
                    if next_url
                    else url_for("photos.import_chat")
                )
        else:
            if "json_file" not in request.files:
                flash(
                    "Укажите JSON: загрузите файл или введите полный путь к result.json на сервере.",
                    "error",
                )
                return redirect(
                    url_for("photos.import_chat", next=next_url)
                    if next_url
                    else url_for("photos.import_chat")
                )
            json_file = request.files["json_file"]
            if not json_file.filename:
                flash(
                    "JSON-файл не выбран (или укажите путь к result.json на диске сервера).",
                    "error",
                )
                return redirect(
                    url_for("photos.import_chat", next=next_url)
                    if next_url
                    else url_for("photos.import_chat")
                )
            if not json_file.filename.lower().endswith(".json"):
                flash(
                    "Файл должен быть в формате JSON (result.json из экспорта Telegram Desktop).",
                    "error",
                )
                return redirect(url_for("photos.import_chat"))
            try:
                json_file.seek(0)
                chat_data = json.load(json_file)
                json_label = json_file.filename
                logger.info("JSON прочитан из загрузки: %s", json_label)
            except json.JSONDecodeError as e:
                flash(f"Ошибка разбора JSON: {e}", "error")
                return redirect(url_for("photos.import_chat"))

        logger.info("Указанный путь к медиа: %s", media_path)
        if not media_path or not os.path.isdir(media_path):
            flash(
                "Укажите существующую папку с файлами экспорта (обычно та же, где лежит result.json, "
                "с подпапками photos, video_files).",
                "error",
            )
            logger.warning("import_chat: media_path не папка: %s", media_path)
            return redirect(url_for("photos.import_chat"))

        export_chat_id = None
        ecid = chat_data.get("id") if isinstance(chat_data, dict) else None
        if ecid is not None:
            export_chat_id = str(ecid)

        try:
            imported_media = 0
            skipped_missing = 0
            skipped_duplicate = 0
            skipped_bad_date = 0
            skipped_not_downloaded = 0

            for message in chat_data.get("messages", []):
                if message.get("type") != "message":
                    continue

                try:
                    message_date = _parse_telegram_export_date(message.get("date"))
                except (ValueError, TypeError) as e:
                    skipped_bad_date += 1
                    logger.debug("Пропуск сообщения: дата: %s", e)
                    continue

                author_name = message.get("from")
                author_id = None
                if message.get("from_id") is not None:
                    telegram_id = str(message["from_id"]).replace("user", "").replace("channel", "")
                    tg_user = TelegramBotUsers.query.filter_by(telegram_id=telegram_id).first()
                    if tg_user:
                        author_id = tg_user.user_id

                description = telegram_export_text_to_plain(message.get("text"))
                file_path = message.get("photo") or message.get("file")
                content_type = (message.get("mime_type") or "") or ""
                file_size = message.get("photo_file_size") or message.get("file_size")
                width = message.get("width")
                height = message.get("height")

                # Telegram writes placeholders in JSON when attachment was not downloaded during export:
                # "(File not included...)" / "(File exceeds maximum size...)"
                if not file_path:
                    continue
                if isinstance(file_path, str) and file_path.startswith("("):
                    skipped_not_downloaded += 1
                    continue

                if file_path.startswith("photos/"):
                    file_type = "photo"
                    target_dir = "static/uploads/photos"
                    db_file_path = f"uploads/photos/{os.path.basename(file_path)}"
                elif file_path.startswith("video_files/") or "video" in content_type.lower():
                    file_type = "video"
                    target_dir = "static/uploads/videos"
                    db_file_path = f"uploads/videos/{os.path.basename(file_path)}"
                else:
                    file_type = "document"
                    target_dir = "static/uploads/documents"
                    db_file_path = f"uploads/documents/{os.path.basename(file_path)}"

                source_file = _resolve_export_media_file(media_path, file_path)
                if not source_file:
                    skipped_missing += 1
                    logger.warning(
                        "Файл не найден в экспорте: %s (папка %s)", file_path, media_path
                    )
                    continue

                target_file_dir = os.path.join(current_app.root_path, target_dir)
                os.makedirs(target_file_dir, exist_ok=True)
                target_file = os.path.join(target_file_dir, os.path.basename(file_path))

                shutil.copy2(source_file, target_file)

                if Media.query.filter_by(file_path=db_file_path).first():
                    skipped_duplicate += 1
                    continue

                request_id = None
                if description:
                    match = re.search(r"#заявка(\d+)", description)
                    if match:
                        request_number = match.group(1)
                        req = Request.query.filter_by(request_number=request_number).first()
                        if req:
                            request_id = req.id

                if file_type == "photo" and (not width or not height):
                    try:
                        with Image.open(target_file) as img:
                            width, height = img.size
                    except Exception as e:
                        logger.warning("Размеры изображения %s: %s", target_file, e)

                msg_tid = message.get("id")
                try:
                    telegram_message_id = int(msg_tid) if msg_tid is not None else None
                except (TypeError, ValueError):
                    telegram_message_id = None

                media = Media(
                    file_path=db_file_path,
                    file_type=file_type,
                    upload_date=message_date,
                    description=description,
                    created_by_user_id=author_id,
                    author_name=author_name,
                    category="work",
                    width=width,
                    height=height,
                    file_size=file_size,
                    content_type=content_type or None,
                    request_id=request_id,
                    chat_id=export_chat_id,
                    telegram_message_id=telegram_message_id,
                )
                db.session.add(media)
                imported_media += 1

            db.session.add(
                SystemLogs(
                    created_at=datetime.now(),
                    level="INFO",
                    message=f"Импорт чата ({json_label}): добавлено {imported_media} медиа",
                )
            )
            db.session.commit()

            parts = [
                f"Импорт завершён: добавлено новых файлов в галерею — {imported_media}.",
                f"Не найдено на диске (проверьте путь к папке экспорта): {skipped_missing}.",
                f"Уже были в базе (пропуск): {skipped_duplicate}.",
            ]
            if skipped_not_downloaded:
                parts.append(
                    f"В экспорте отсутствуют вложения (не были скачаны Telegram): {skipped_not_downloaded}."
                )
            if skipped_bad_date:
                parts.append(f"Пропущено из‑за даты: {skipped_bad_date}.")
            msg = " ".join(parts)

            if imported_media == 0:
                flash(
                    msg
                    + " Если файлов много, укажите путь к result.json на диске сервера (поле ниже), "
                    "а папку — корень экспорта с подпапкой photos.",
                    "warning",
                )
            else:
                flash(msg, "success" if skipped_missing == 0 else "warning")

            logger.info(
                "Импорт чата: +%s медиа, пропуск не найдено=%s, дубликаты=%s",
                imported_media,
                skipped_missing,
                skipped_duplicate,
            )
            if next_url:
                return redirect(next_url)
            return redirect(url_for("photos.photos_list"))

        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при импорте чата: {str(e)}", "error")
            logger.exception("Ошибка при импорте чата")
            try:
                db.session.add(
                    SystemLogs(
                        created_at=datetime.now(),
                        level="ERROR",
                        message=f"Ошибка при импорте чата: {str(e)}",
                    )
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
            return redirect(
                url_for("photos.import_chat", next=next_url)
                if next_url
                else url_for("photos.import_chat")
            )

    return render_template("photos/import_chat.html", next_url=next_url)


@photos_bp.route("/import_chat/browse", methods=["GET"])
@login_required
def import_chat_browse():
    path = request.args.get("path", "")
    try:
        return jsonify(browse_directory(path))
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except OSError as e:
        logger.warning("import_chat_browse: %s", e)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("import_chat_browse")
        return jsonify({"error": str(e)}), 500


@photos_bp.route("/edit/<int:photo_id>", methods=["GET", "POST"])
@login_required
def edit_photo(photo_id):
    try:
        if request.method == "POST":
            client_id = _int_or_none(request.form.get("client_id"))
            request_id = _int_or_none(request.form.get("request_id"))
            equipment_id = _int_or_none(request.form.get("equipment_id"))
            description = (request.form.get("description") or "").strip() or None
            equipment_type = (request.form.get("equipment_type") or "").strip() or None
            category = (request.form.get("category") or "").strip() or None

            media = db.session.query(Media).filter_by(id=photo_id).first()
            if not media:
                flash("Медиа не найдено", "error")
                logger.warning(f"Медиа ID={photo_id} не найдено")
                db.session.add(
                    SystemLogs(
                        created_at=datetime.now(),
                        level="WARNING",
                        message=f"Медиа ID={photo_id} не найдено",
                    )
                )
                db.session.commit()
                return redirect(url_for("photos.photos_list"))

            if request_id and client_id:
                req_row = db.session.get(Request, request_id)
                if req_row and req_row.client_id and req_row.client_id != client_id:
                    flash(
                        "Выбранная заявка относится к другому клиенту; привязка к заявке сброшена.",
                        "warning",
                    )
                    request_id = None
            elif request_id and not client_id:
                req_row = db.session.get(Request, request_id)
                if req_row and req_row.client_id:
                    client_id = req_row.client_id

            media.client_id = client_id
            media.request_id = request_id
            media.equipment_id = equipment_id
            media.description = description
            media.equipment_type = equipment_type
            media.category = category
            db.session.commit()

            flash("Медиа успешно обновлено", "success")
            logger.info(
                f"Успешно обновлено медиа ID={photo_id}, client_id={client_id}, description={description}, equipment_type={equipment_type}"
            )
            db.session.add(
                SystemLogs(
                    created_at=datetime.now(),
                    level="INFO",
                    message=f"Обновлено медиа ID={photo_id}, client_id={client_id}, description={description}, equipment_type={equipment_type}",
                )
            )
            db.session.commit()
            dest = _safe_relative_next()
            if dest:
                return redirect(dest)
            return redirect(url_for("photos.photos_list"))

        media = db.session.query(Media).filter_by(id=photo_id).first()
        if not media:
            flash("Медиа не найдено", "error")
            logger.warning(f"Медиа ID={photo_id} не найдено")
            db.session.add(
                SystemLogs(
                    created_at=datetime.now(),
                    level="WARNING",
                    message=f"Медиа ID={photo_id} не найдено",
                )
            )
            db.session.commit()
            return redirect(url_for("photos.photos_list"))

        if media.client_id:
            req_rows = (
                Request.query.filter_by(client_id=media.client_id)
                .order_by(Request.created_at.desc())
                .limit(500)
                .all()
            )
            equipment = (
                Equipment.query.filter_by(client_id=media.client_id)
                .order_by(Equipment.serial_number)
                .all()
            )
        else:
            req_rows = Request.query.order_by(Request.created_at.desc()).limit(300).all()
            equipment = Equipment.query.order_by(Equipment.serial_number).limit(500).all()

        next_url = _safe_relative_next()
        client_picker_label = ""
        if media.client:
            client_picker_label = f"{media.client.full_name or '—'} · {media.client.phone or '—'}"

        return render_template(
            "photos/edit.html",
            photo=media,
            requests=req_rows,
            equipment=equipment,
            next_url=next_url,
            client_picker_label=client_picker_label,
        )
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка: {str(e)}", "error")
        logger.error(f"Ошибка при редактировании медиа ID={photo_id}: {str(e)}")
        db.session.add(
            SystemLogs(
                created_at=datetime.now(),
                level="ERROR",
                message=f"Ошибка при редактировании медиа ID={photo_id}: {str(e)}",
            )
        )
        db.session.commit()
        return redirect(url_for("photos.photos_list"))


@photos_bp.route("/delete", methods=["POST"])
@login_required
def delete_photos():
    photo_ids = request.form.getlist("photo_ids")
    if not photo_ids:
        flash("Файлы не выбраны", "error")
        logger.warning("Попытка удаления медиа без выбора файлов")
        db.session.add(
            SystemLogs(
                created_at=datetime.now(),
                level="WARNING",
                message="Попытка удаления медиа без выбора файлов",
            )
        )
        db.session.commit()
        return redirect(url_for("photos.photos_list"))

    try:
        photo_ids = [int(pid) for pid in photo_ids]
    except ValueError:
        flash("Некорректные ID медиа", "error")
        logger.error(f"Некорректные ID медиа для удаления: {photo_ids}")
        return redirect(url_for("photos.photos_list"))

    try:
        media_records = db.session.query(Media).filter(Media.id.in_(photo_ids)).all()
        file_paths = [media.file_path for media in media_records]

        db.session.query(Media).filter(Media.id.in_(photo_ids)).delete(synchronize_session=False)
        db.session.commit()
        deleted_count = len(media_records)

        deleted_files = []
        for file_path in file_paths:
            full_path = _absolute_media_disk_path(file_path)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    deleted_files.append(full_path)
                except Exception as e:
                    logger.error(f"Ошибка при удалении файла {full_path}: {str(e)}")
            else:
                logger.warning(f"Файл не найден: {full_path}")

        flash(f"Файлы успешно удалены: {deleted_count}", "success")
        logger.info(f"Успешно удалены медиа: {photo_ids}, файлы: {deleted_files}")
        db.session.add(
            SystemLogs(
                created_at=datetime.now(),
                level="INFO",
                message=f"Удалены медиа: {photo_ids}, файлы: {deleted_files}",
            )
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка: {str(e)}", "error")
        logger.error(f"Ошибка при удалении медиа {photo_ids}: {str(e)}")
        db.session.add(
            SystemLogs(
                created_at=datetime.now(),
                level="ERROR",
                message=f"Ошибка при удалении медиа {photo_ids}: {str(e)}",
            )
        )
        db.session.commit()
        return redirect(url_for("photos.photos_list"))

    return redirect(url_for("photos.photos_list"))


@photos_bp.route("/attach_to_request", methods=["POST"])
@login_required
def attach_to_request():
    photo_ids = request.form.getlist("photo_ids")
    request_id = request.form.get("request_id")

    if not photo_ids:
        flash("Файлы не выбраны", "error")
        logger.warning("Попытка привязки медиа без выбора файлов")
        return redirect(url_for("photos.photos_list"))

    if not request_id:
        flash("Заявка не выбрана", "error")
        logger.warning("Попытка привязки медиа без выбора заявки")
        return redirect(url_for("photos.photos_list"))

    try:
        photo_ids = [int(pid) for pid in photo_ids]
        request_id = int(request_id)
    except ValueError:
        flash("Некорректные ID медиа или заявки", "error")
        logger.error(
            f"Некорректные ID медиа или заявки: photo_ids={photo_ids}, request_id={request_id}"
        )
        return redirect(url_for("photos.photos_list"))

    try:
        request = db.session.query(Request).filter_by(id=request_id).first()
        if not request:
            flash("Заявка не найдена", "error")
            logger.warning(f"Заявка ID={request_id} не найдена")
            return redirect(url_for("photos.photos_list"))

        updated = (
            db.session.query(Media)
            .filter(Media.id.in_(photo_ids))
            .update({Media.request_id: request_id}, synchronize_session=False)
        )
        db.session.commit()

        flash(f"Медиа успешно привязаны к заявке: {updated}", "success")
        logger.info(f"Медиа привязаны к заявке ID={request_id}: {photo_ids}")
        db.session.add(
            SystemLogs(
                created_at=datetime.now(),
                level="INFO",
                message=f"Медиа привязаны к заявке ID={request_id}: {photo_ids}",
            )
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка: {str(e)}", "error")
        logger.error(f"Ошибка при привязке медиа к заявке ID={request_id}: {str(e)}")
        db.session.add(
            SystemLogs(
                created_at=datetime.now(),
                level="ERROR",
                message=f"Ошибка при привязке медиа к заявке ID={request_id}: {str(e)}",
            )
        )
        db.session.commit()
        return redirect(url_for("photos.photos_list"))

    return redirect(url_for("photos.photos_list"))


@photos_bp.route("/rename_author", methods=["POST"])
@login_required
def rename_author():
    old_author = (request.form.get("old_author") or "").strip()
    new_author = (request.form.get("new_author") or "").strip()
    only_bot = request.form.get("only_bot") == "1"

    if not old_author or not new_author:
        flash("Укажите старое и новое имя автора", "error")
        return redirect(url_for("photos.photos_list"))

    if old_author == new_author:
        flash("Старое и новое имя совпадают", "warning")
        return redirect(url_for("photos.photos_list"))

    try:
        query = db.session.query(Media).filter(
            func.lower(func.trim(Media.author_name)) == old_author.lower(),
        )
        if only_bot:
            query = query.filter(Media.chat_id.isnot(None))

        updated = query.update({Media.author_name: new_author}, synchronize_session=False)
        db.session.commit()

        scope = "только Telegram-импорт" if only_bot else "все источники"
        flash(f"Переименование выполнено: {updated} записей ({scope})", "success")
        db.session.add(
            SystemLogs(
                created_at=datetime.now(),
                level="INFO",
                message=f'Массовое переименование автора: "{old_author}" -> "{new_author}", изменено: {updated}, scope={scope}',
            )
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка переименования автора: {str(e)}", "error")
        logger.error("Ошибка переименования автора: %s", e)

    return redirect(url_for("photos.photos_list"))


@photos_bp.route("/view/<int:id>")
@login_required
def view(id):
    try:
        media = db.session.query(Media).get_or_404(id)
        full_path = _absolute_media_disk_path(media.file_path)
        if not full_path or not os.path.isfile(full_path):
            logger.warning(f"Файл не найден: {media.file_path} -> {full_path}")
            flash("Файл не найден", "error")
            return redirect(url_for("photos.photos_list"))
        directory = os.path.dirname(full_path)
        filename = os.path.basename(full_path)
        return send_from_directory(directory, filename)
    except Exception as e:
        logger.error(f"Ошибка в view медиа ID={id}: {str(e)}")
        flash(f"Ошибка: {str(e)}", "error")
        return redirect(url_for("photos.photos_list"))
