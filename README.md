# UtilBase

<p align="center">
  <img src="app/static/images/utilbase-logo.png" alt="UtilBase logo" width="220">
</p>

Веб‑приложение для сервисных компаний: учёт клиентов, заявок, оборудования и работы выездных бригад. Основа для собственной CRM / FSM‑системы на Python + Flask.

UtilBase работает в связке **веб‑панели диспетчера/офиса** и **мобильного приложения исполнителя**: офис планирует и контролирует заявки, а полевая команда получает задачи, ведёт статусы по шагам, прикладывает фото/видео и фиксирует результаты работ (в т.ч. с поддержкой offline‑очереди / outbox).

**Перспектива развития** — расширение системы под конкретные бизнес‑процессы заказчика: модуль **склада/учёта материалов и списаний**, **мини‑бухгалтерия** (платежи, взаиморасчёты, акты/счета), **запись и привязка звонков** к клиентам/заявкам, а также любые дополнительные сценарии, которые нужны для автоматизации (интеграции, отчётность, контроль качества, SLA, маршрутизация, уведомления).

---

## Что умеет UtilBase

- **Клиенты и объекты** — карточка клиента, договоры, привязка оборудования, заявок, платежей и медиа.

- **Заявки и календарь** — исполнители у заявки **необязательны**; статусы в т.ч. **«Отменена»**. План‑график: заявки + слой **смен из таблицы `worker_shifts`** (задаётся на подвкладке исполнителей, не связан с заявками). Подвкладка **«Исполнители»** — смены из БД + полосы заявок с назначенными людьми (поверх). Пункт «Исполнители» в боковой панели убран — доступ через план‑график. **Google Calendar** не встроен. Мягкое увольнение исполнителей без потери истории.

- **Оборудование** — иерархия, шаблоны, импорт из Excel, расчёт объёма обслуживания.

- **Исполнители и роли** — workers; роли `admin`, `engineer`, `master`; админка и демо‑данные.

- **Медиа и нормативы**
  - загрузка фото/видео/документов, привязка к клиентам, заявкам и оборудованию;
  - **Telegram‑бот**: скачивание из групп/каналов в `media`, учёт `chat_id` и `telegram_message_id`, панель `/telegram-bot/` (admin);
  - **импорт из экспорта Telegram Desktop (JSON)** — см. [Импорт экспорта Telegram](#импорт-экспорта-telegram-кратко); подписи из поля `text` разбираются и при строковом, и при **массиве фрагментов** (как в примере `docs/telegram-json-ui`);
  - **раздел «Фото»** (`/photos/`): список с **пагинацией**, сетка **6 колонок**, ленивые превью; поиск по подписи с режимом **«контекст»** (соседние кадры в том же чате, **тот же календарный день** и **тот же автор**, плюс ±сообщений / ±минут);
  - **массовое переименование автора** (ник → имя) для уже импортированных записей;
  - раздел «Справочный материал» и поиск по тексту (spaCy).

- **Карта** — Yandex Maps, фильтры по объектам и оборудованию.

- **Демо** — `/demo` и кнопки в админке для демо‑данных.

---

## Импорт экспорта Telegram (кратко)

Нужен экспорт **JSON** из Telegram Desktop (файл `result.json`), не HTML.

1. **Папка с медиа** (обязательно) — корень папки экспорта, где лежит `result.json` рядом с подпапками `photos`, `video_files`, `files` (например `F:\Telegram arhiv\ChatExport_2026-03-19`). Кнопка **«Обзор…»** открывает **обзор папок на машине сервера** (где запущен Flask), не в облаке.

2. **JSON** — один из вариантов:
   - загрузить небольшой `result.json` через поле файла;
   - или указать **полный путь к `result.json` на диске сервера** (для больших архивов загрузка через браузер может не пройти — см. `MAX_CONTENT_LENGTH_MB` в `.env`).

3. В форме при импорте показывается индикатор ожидания; после импорта — сообщение со сколько файлов добавлено, сколько не найдено на диске, сколько дубликатов, сколько записей без вложений (заглушки вроде «File exceeds maximum size…» в экспорте — такие вложения в архив не попали, их нужно пересобрать экспортом с большим лимитом размера в настройках Telegram).

4. Ограничение обзора папок (опционально): `IMPORT_BROWSER_ROOTS` в `.env` — список корней через запятую.

Страница импорта: **Фото → Импорт чата** (`/photos/import_chat`).

---

## Установка и запуск

### Вариант 1 (Windows)

```bash
git clone https://github.com/StormUltimate/UtilBase.git
```

Далее `install.bat` в корне проекта:

1. создаёт `venv`, ставит зависимости, копирует `.env.example` → `.env`, применяет `flask db upgrade`;
2. отредактируйте `.env` (PostgreSQL и при необходимости ключи);
3. запустите `start run.bat` — откроется `http://127.0.0.1:5000`.

### Вариант 2. Ручная установка

```bash
git clone https://github.com/StormUltimate/UtilBase.git
cd UtilBase
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
rem отредактируйте .env (БД, ключи)
set FLASK_APP=run:app
flask db upgrade
python run.py
```

---

## Конфигурация

Все чувствительные данные — в `.env`:

| Переменная | Назначение |
|------------|------------|
| `SECRET_KEY` | секрет Flask |
| `JWT_SECRET_KEY` | JWT |
| `SQLALCHEMY_DATABASE_URI` | PostgreSQL |
| `BOT_TOKEN` | токен бота для медиа из чатов |
| `TELEGRAM_ADMIN_IDS` | ID для `/stats` и `/channels` |
| `BASE_DIR` | корень проекта (по умолчанию авто) |
| `YANDEX_API_KEY` | карты |
| `MAX_CONTENT_LENGTH_MB` | лимит загрузки JSON при импорте через браузер (по умолчанию 512) |
| `IMPORT_BROWSER_ROOTS` | опционально: разрешённые корни для обзора папок при импорте (через запятую) |

В репозитории только `.env.example`, `.env` в Git не коммитится.

---

## Миграции БД

```bash
set FLASK_APP=run:app
flask db upgrade
```

---

## Mobile API v1 (ядро под Android)

Базовый контур API для мобильного исполнителя:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/requests` (для исполнителя по умолчанию **active** — без закрытых и отменённых; явно `filter=all` — всё), `GET /api/v1/requests/<id>`
- `POST /api/v1/requests/<id>/take` (при гонке двух исполнителей — **409** `already_assigned`)
- `POST /api/v1/requests/<id>/mode` — цепочка в т.ч. **on_way → arrived → in_progress → …**
- `POST /api/v1/requests/<id>/close`
- `GET|POST /api/v1/requests/<id>/media` (POST multipart, опционально **category** для типа вложения)
- `GET|POST /api/v1/requests/<id>/defects` (дефект оборудования/материала, опционально `media_id`)
- `GET|POST|PATCH|DELETE /api/v1/requests/<id>/items...`
- `GET|POST /api/v1/requests/<id>/payments`
- `GET|POST /api/v1/requests/<id>/chat/messages`
- `GET /api/v1/requests/<id>/checklist-template`
- `POST /api/v1/requests/<id>/checklist-submit`
- `GET /api/v1/requests/<id>/logs`

### Offline / outbox (идемпотентность)

Для mutation-endpoint'ов передавайте `client_operation_id` (UUID):

- в JSON поле `client_operation_id`, или
- в multipart поле `client_operation_id`, или
- в заголовке `X-Client-Operation-Id`.

Сервер хранит операции в `request_client_operations` и не применяет дубликаты повторно.

### Коды ошибок (минимальный контракт)

- `validation_error` — некорректные данные запроса.
- `invalid_state` — операция невозможна из текущего состояния заявки.
- `conflict_fsm` — нарушение FSM/правил закрытия (не тот шаг, нет фото, не заполнен обязательный чек-лист).
- `already_assigned` — заявку уже взял другой исполнитель (часто **409** на `take`).
- `forbidden` — нет прав доступа.
- `not_found` — сущность не найдена.
- `server_error` — внутренняя ошибка сервера.

### HTTPS only

Для production включайте:

- `API_FORCE_HTTPS=true`

Тогда API будет отклонять HTTP-запросы с кодом `426` (`https_required`), а web-часть перенаправляется на HTTPS.

### Документы для Android-интеграции

- Контракт API/Outbox: `docs/mobile_api_contract.md`
- OpenAPI: `docs/openapi_v1.yaml`
- Payload examples: `docs/mobile_payload_examples.md`
- Retry matrix: `docs/mobile_retry_matrix.md`
- Room/outbox schema: `docs/android_outbox_schema.md`
- Kotlin starter (DTO + Retrofit): `docs/android_kotlin_starter.md`

---

## Роли и доступ

- **admin** — полный доступ, админка, Telegram‑бот, импорт чата.
- **engineer**, **master** — заявки, календарь, фото, карта.

Стартовый пользователь: `admin` / `admin` — смените пароль.

---

## Технологический стек

Python 3.10+, Flask, PostgreSQL, SQLAlchemy, Flask‑Migrate, Flask‑Login, Flask‑JWT‑Extended, spaCy, Bootstrap 5, и др. (см. `requirements.txt`).

---

## Структура проекта (кратко)

- `app/` — код приложения (`blueprints`, `models`, `templates`, `static`, `utils`);
- `migrations/` — Alembic;
- `android-app/` — Android проект (Kotlin, Retrofit, Room, WorkManager, Compose);
- `docs/` — вспомогательные материалы (в т.ч. `docs/telegram-json-ui`, `docs/README.md`);
- `install.bat`, `start run.bat` — запуск на Windows.

---

## Android: где проект и как собрать APK

Папка Android-проекта: `android-app/`.

Как открыть:

1. В Android Studio: **Open** -> выбрать папку `V:\UtilBase\android-app`.
2. Дождаться Gradle Sync.
3. При необходимости задать URL API в `android-app/app/build.gradle.kts`:
   - `UTILBASE_BASE_URL`, по умолчанию: `http://10.0.2.2:5000/api/v1/`.

Сборка APK:

- Debug APK (через Android Studio): **Build -> Build APK(s)**.
- Debug APK (CLI):

```bash
cd android-app
gradlew.bat assembleDebug
```

APK будет в:

- `android-app/app/build/outputs/apk/debug/app-debug.apk`

---

## Navigation QA (практика)

Чтобы не ловить регрессии по кнопкам `Назад`, используем 2 уровня проверки:

1. **Матрица ручных сценариев** (перед релизом):

| Откуда вошли | Экран | Действие | Ожидаемый возврат |
|---|---|---|---|
| `clients/detail/<id>#tab-equipment` | `equipment/edit/<id>` | Назад / Сохранить | `clients/detail/<id>#tab-equipment` |
| `clients/detail/<id>#tab-requests` | `requests/view/<id>` | Назад | `clients/detail/<id>#tab-requests` |
| `requests/list` или `requests/today` | `requests/view/<id>?next=...` | Назад | исходный список/фильтр |
| `requests/view/<id>` | `requests/edit/<id>` | Отмена / Сохранить | `requests/view/<id>` |
| `admin` | `users/edit/<id>` | Отмена / Сохранить | `admin` |
| `admin` | `workers/edit/<id>` | Отмена / Сохранить | `admin` |
| `clients/detail/<id>#tab-photos` | `photos/edit/<id>?next=...` | Назад / Сохранить | `clients/detail/<id>#tab-photos` |
| `contracts/list` | `contracts/<id>?next=...` | Назад | `contracts/list` |
| `contracts/<id>` | `contracts/<id>/edit?next=...` | К договору / Сохранить | `contracts/<id>` |
| `photos` | `photos/upload|import_chat?next=...` | Назад / После действия | `photos` |

2. **Автопроверка конвенций** (локально в CI или перед коммитом):

```bash
python -m unittest discover -s tests -p "test_navigation_conventions.py" -v
```

Что проверяется автоматически:

- в `equipment` шаблонах нет артефактов вида `Path: ...`;
- в `url_for('clients.client_detail', ...)` не используется неверный параметр `id=`;
- в ключевых местах ссылки на `edit_*` передают `next=...`.

Это не заменяет e2e, но быстро ловит самые частые поломки навигации.

---

## Лицензия

**MIT** — см. `LICENSE`.
