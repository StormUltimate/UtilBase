# UtilBase

Веб‑приложение для сервисных компаний: учёт клиентов, заявок,
оборудования и работы выездных бригад. Основа для собственной CRM /
FSM‑системы на Python + Flask.

---

## Что умеет UtilBase

- **Клиенты и объекты**
  - карточка клиента с контактами, адресом и координатами;
  - несколько договоров на одного клиента;
  - привязка оборудования, заявок, платежей и медиафайлов.

- **Заявки и календарь**
  - создание и редактирование заявок с типом услуги и приоритетом;
  - фильтрация по статусу, типу, дате и исполнителям;
  - автоматическая пометка просроченных заявок;
  - календарь заявок (план‑график) с перетаскиванием задач мышкой.

- **Оборудование**
  - иерархия оборудования по клиентам;
  - шаблоны типовых единиц и массовый импорт из Excel;
  - параметры мощности, года выпуска, сервисных интервалов;
  - расчёт годового объёма обслуживания.

- **Исполнители и роли**
  - отдельный список исполнителей (workers);
  - роли пользователей: admin, engineer, master;
  - админ‑панель с управлением пользователями, исполнителями и
    демо‑данными.

- **Медиа и нормативы**
  - загрузка фото, видео и документов, привязка к клиентам, заявкам и
    оборудованию;
  - импорт медиа из экспорта Telegram;
  - раздел «Справочный материал» с файлами и ссылками + поиск по тексту
    (spaCy).

- **Карта**
  - отображение клиентов и оборудования на карте (Yandex Maps);
  - фильтры по типу объектов и оборудованию.

- **Демо‑режим**
  - отдельная страница `/demo` с полностью фейковыми данными;
  - в админке есть кнопки создать/очистить демо‑данные в базе (клиенты,
    заявки, исполнители, псевдо‑фото без файлов).

---



---

## Установка и запуск
### Вариант 1.
'''bash  (cmd)
git clone https://github.com/StormUltimate/UtilBase.git
потом через `install.bat` (Windows)

После клонирования репозитория:

1. Запустите `install.bat` в корне проекта:
   - создаст виртуальное окружение `venv`;
   - установит зависимости из `requirements.txt`;
   - скопирует `.env.example` в `.env`;
   - попробует применить миграции `flask db upgrade`.
2. Откройте `.env` и пропишите свои данные подключения к PostgreSQL.
3. Запустите `start run.bat`:
   - активирует venv;
   - запустит приложение;
   - откроет `http://127.0.0.1:5000` в браузере.

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

Все чувствительные данные выносятся в `.env`:

- `SECRET_KEY` — секретный ключ Flask;
- `JWT_SECRET_KEY` — ключ для JWT‑токенов;
- `SQLALCHEMY_DATABASE_URI` — строка подключения к PostgreSQL
  (`postgresql://user:password@host:port/utilbase`);
- `BOT_TOKEN` — токен Telegram‑бота (опционально, можно оставить пустым);
- `BASE_DIR` — путь к проекту (по умолчанию вычисляется автоматически);
- `YANDEX_API_KEY` — ключ для Yandex Maps.

В репозитории лежит только `.env.example`, `.env` игнорируется Git‑ом.

---

## Миграции БД

Схема базы поддерживается через Flask‑Migrate / Alembic:

```bash
set FLASK_APP=run:app
flask db upgrade
```

Начальная миграция создаёт все таблицы, остальные миграции добавляют
эволюционные изменения и демо‑данные для календаря.

---

## Роли и доступ

- **admin**
  - полный доступ ко всем разделам;
  - управление пользователями, исполнителями, демо‑данными;
  - просмотр и редактирование клиентов, заявок, оборудования, медиа,
    нормативов.

- **engineer**, **master**
  - работа со своими заявками и календарём;
  - доступ к фото и карте объектов;
  - нет доступа к админ‑панели.

Стартовый пользователь создаётся при первом запуске:

- логин: `admin`
- пароль: `admin`

Рекомендуется сразу изменить пароль через раздел управления
пользователями.

---

## Технологический стек

- Python 3.10+, Flask;
- PostgreSQL, SQLAlchemy, Flask‑Migrate;
- Flask‑Login, Flask‑JWT‑Extended;
- Flask‑WTF, Flask‑CORS, Flask‑Limiter, flask‑paginate;
- Flask‑SocketIO (для чата и real‑time‑сценариев, при необходимости);
- spaCy + pymorphy3 для русского NLP;
- Bootstrap 5, Bootstrap Icons, собственные CSS/JS.

---

## Структура проекта (кратко)

- `app/` — основной код приложения:
  - `blueprints/` — маршруты и UI по разделам;
  - `models/` — SQLAlchemy‑модели;
  - `templates/` — Jinja2‑шаблоны;
  - `static/` — CSS, JS, изображения, манифест, сервис‑воркер;
  - `utils/` — служебные задачи (демо‑данные, PDF, планировщик).
- `migrations/` — миграции Alembic.
- `install.bat`, `start run.bat` — удобный запуск на Windows.

---

## Лицензия

Проект распространяется по лицензии **MIT** — см. файл `LICENSE`.

# UtilBase

Веб-приложение для учёта заявок, клиентов, оборудования и работы сервисной
службы. Flask, PostgreSQL, Bootstrap 5.

---

## Быстрый старт (Windows)

После клонирования репозитория:

1. Запустите **`install.bat`** — создание venv, установка зависимостей,
   копирование `.env.example` в `.env`, применение миграций.
2. Отредактируйте **`.env`** (подключение к БД, ключи API).
3. Запустите **`start run.bat`** — старт сервера и автоматическое открытие
   http://127.0.0.1:5000 в браузере.

---

## Требования

- Python 3.10+
- PostgreSQL
- Переменные окружения (см. раздел «Конфигурация»)

---

## Установка вручную

```bash
git clone https://github.com/your-username/UtilBase.git
cd UtilBase
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env
# Отредактируйте .env
set FLASK_APP=run.py
flask db upgrade
python run.py
```

Для spaCy с русской моделью используется ссылка в `requirements.txt`
(ru_core_news_sm).

---

## Конфигурация

Скопируйте `.env.example` в `.env` и задайте значения:

| Переменная                 | Описание                        |
|---------------------------|---------------------------------|
| `SECRET_KEY`              | Секретный ключ Flask            |
| `JWT_SECRET_KEY`          | Секрет для JWT-токенов          |
| `SQLALCHEMY_DATABASE_URI` | URL подключения к PostgreSQL    |
| `BOT_TOKEN`               | Токен Telegram-бота (опционально) |
| `BASE_DIR`                | Путь к проекту (опционально)    |
| `YANDEX_API_KEY`          | Ключ Yandex API (карты)         |

---

## Запуск

- **Режим разработки:** `start run.bat` (Windows) или `python run.py`.
  Браузер откроется на http://127.0.0.1:5000 автоматически.
- **Продакшен (Gunicorn):**
  `gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:5000 "run:app"`.

При первом запуске создаётся пользователь: логин `admin`, пароль `admin`
— смените после входа.

---

## Миграции БД

```bash
set FLASK_APP=run.py
flask db upgrade
```

---

## Описание модулей и функций

### 1. Аутентификация (auth)

| Функция | Маршрут   | Метод     | Описание                          |
|---------|-----------|-----------|-----------------------------------|
| Вход    | /login    | GET, POST | Форма входа, редирект на /clients/ |
| Выход   | /logout   | GET       | Выход из системы                  |

Шаблон: `auth/login.html`.

---

### 2. Пользователи (users) — только admin

| Функция             | Маршрут            | Метод     | Описание                |
|---------------------|--------------------|-----------|-------------------------|
| Список              | /users/            | GET       | Таблица пользователей   |
| Добавить            | /users/add         | GET, POST | username, password, role |
| Редактировать       | /users/edit/<id>   | GET, POST | Изменение данных        |
| Удалить             | /users/delete      | GET, POST | Форма выбора            |

Шаблоны: `users/list.html`, `users/add.html`, `users/edit.html`,
`users/delete.html`.

---

### 3. Клиенты (clients)

| Функция             | Маршрут                  | Метод     | Описание              |
|---------------------|--------------------------|-----------|-----------------------|
| Список              | /clients/                | GET       | Поиск, сортировка     |
| Добавить            | /clients/add             | GET, POST | Форма + геокодирование |
| Редактировать       | /clients/edit/<id>       | GET, POST | Редактирование        |
| Удалить             | /clients/delete          | GET, POST | Форма выбора          |
| Карточка клиента    | /clients/detail/<id>     | GET       | Заявки, договоры, фото |
| Карта клиента       | /clients/map/<id>        | GET       | Карта по координатам   |
| Экспорт Excel       | /clients/export          | GET       | Выгрузка в .xlsx      |
| Импорт Excel        | /clients/import          | POST      | Загрузка .xlsx        |
| Обновить координаты | /clients/update_coords/<id> | POST (JSON) | Ajax lat/long    |

Шаблоны: `clients/list.html`, `clients/add.html`, `clients/edit.html`,
`clients/delete.html`, `clients/detail.html`, `clients/map.html`.

---

### 4. Заявки (requests)

| Функция           | Маршрут                         | Метод     | Описание           |
|-------------------|---------------------------------|-----------|--------------------|
| Список            | /requests/list                 | GET       | Фильтры заявок     |
| Заявки сегодня    | /requests/today                | GET       | Расширенные фильтры |
| Добавить          | /requests/add                  | GET, POST | Создание заявки    |
| Просмотр          | /requests/view/<id>            | GET       | Детали заявки      |
| Редактировать     | /requests/edit/<id>            | GET, POST | Редактирование     |
| Создать наряд     | /requests/create_work_order/<id> | GET, POST | WorkOrder        |
| Назначить себя    | /requests/assign/<id>          | POST      | Мастер/инженер      |
| Назначить мастера | /requests/assign_worker        | POST      | Admin               |
| Закрыть заявку    | /requests/close/<id>            | POST      | Закрытие            |
| Календарь         | /requests/calendar             | GET       | FullCalendar        |
| API событий       | /requests/api/events           | GET       | JSON для календаря  |
| API обновить дату | /requests/api/update_event     | POST      | Перетаскивание     |
| Поиск клиентов    | /requests/api/search_clients   | GET       | Autocomplete        |

Шаблоны: `requests/list.html`, `requests/list_mobile.html`, `requests/today.html`,
`requests/add.html`, `requests/edit.html`, `requests/view.html`,
`requests/calendar.html`, `requests/calendar_mobile.html`.

Для engineer/master доступны мобильные шаблоны.

---

### 5. Фото/медиа (photos)

| Функция           | Маршрут                 | Метод     | Описание            |
|-------------------|-------------------------|-----------|---------------------|
| Список медиа      | /photos/                | GET       | Фильтры, сортировка |
| Загрузить         | /photos/upload          | GET, POST | Фото/видео/документ |
| Импорт из чата    | /photos/import_chat     | GET, POST | Импорт из Telegram  |
| Редактировать     | /photos/edit/<id>       | GET, POST | Привязка, описание  |
| Удалить           | /photos/delete          | POST      | Массовое удаление   |
| Привязать к заявке| /photos/attach_to_request | POST   | Медиа + заявка      |
| Просмотр файла    | /photos/view/<id>       | GET       | Отдача файла        |

Шаблоны: `photos/photos.html`, `photos/upload.html`, `photos/import_chat.html`,
`photos/edit.html`.

---

### 6. Оборудование (equipment)

| Функция             | Маршрут                            | Метод     | Описание          |
|---------------------|------------------------------------|-----------|-------------------|
| Список              | /equipment/list                   | GET       | Дерево, фильтры   |
| Список по клиенту   | /equipment/client/<id>/list      | GET       | Оборудование клиента |
| Добавить            | /equipment/add                   | GET, POST | Новое оборудование |
| Добавить у клиента  | /equipment/client/<id>/add       | GET, POST | В паспорте клиента |
| Редактировать       | /equipment/edit/<id>             | GET, POST | Редактирование    |
| Удалить             | /equipment/delete/<id>           | POST      | Удаление          |
| Обслуживание        | /equipment/client/<id>/maintenance | GET     | Страница обслуживания |
| Шаблоны — список    | /equipment/templates/list        | GET       | Список шаблонов    |
| Шаблон — добавить   | /equipment/templates/add         | GET, POST | Новый шаблон       |
| Шаблон — редактировать | /equipment/templates/edit/<id> | GET, POST | Редактирование  |
| Шаблон — удалить    | /equipment/templates/delete/<id> | POST      | Удаление шаблона   |
| Поиск шаблонов      | /equipment/templates/search      | GET       | Fuzzy search       |
| Импорт шаблонов     | /equipment/templates/import      | GET, POST | Импорт .xlsx       |
| Иерархия            | /equipment/hierarchy             | GET       | Дерево оборудования |
| Паспорт клиента     | /equipment/client/<id>/passport  | GET, POST | Паспорт + оборудование |
| API поиск           | /equipment/api/equipment/search  | GET       | Поиск для карты    |
| Годовой объём       | /equipment/annual_volume         | GET       | Сумма времени      |
| Экспорт Excel       | /equipment/export_excel          | GET       | Выгрузка           |
| Экспорт шаблонов    | /equipment/templates/export      | GET       | Выгрузка шаблонов  |

Шаблоны: `equipment/list.html`, `equipment/add.html`, `equipment/edit.html`,
`equipment/templates.html`, `equipment/add_template.html`, `equipment/edit_template.html`,
`equipment/import.html`, `equipment/hierarchy.html`, `equipment/client_passport.html`,
`equipment/maintenance.html`, `equipment/annual_volume.html`.

---

### 7. Карта (map)

| Функция       | Маршрут              | Метод     | Описание              |
|---------------|----------------------|-----------|-----------------------|
| Общая карта   | /map                 | GET, POST | Yandex Maps, фильтры  |
| Карта клиента | /map/client/<id>/map | GET, POST | Клиент и оборудование |

Фильтры: тип (clients/equipment/requests/all), тип оборудования, мощность,
дата заявок. Шаблон: `map/map.html`.

---

### 8. Исполнители (workers)

| Функция  | Маршрут              | Метод     | Описание        |
|----------|----------------------|-----------|-----------------|
| Список   | /workers/list        | GET       | Все исполнители |
| Создать  | /workers/create      | GET, POST | full_name, phone, role |
| Удалить  | /workers/delete/<id> | POST      | Удаление        |

Шаблоны: `workers/workers_list.html`, `workers/workers_create.html`.

---

### 9. Нормативы (regulations)

| Функция      | Маршрут                         | Метод     | Описание           |
|--------------|---------------------------------|-----------|--------------------|
| Главная      | /regulations/                   | GET, POST | Загрузка, CRUD ссылок, NLP-поиск |
| Удалить файл | /regulations/delete_file/<name> | POST      | Удаление из uploads |

Загрузка файлов, добавление/редактирование/удаление ссылок, NLP (spaCy).
Шаблон: `regulations/regulations.html`.

---

### 10. Чат (chat)

| Функция   | Маршрут         | Метод     | Описание        |
|-----------|------------------|-----------|-----------------|
| Комнаты   | /chat/           | GET       | Список комнат   |
| Комната   | /chat/room/<id>  | GET       | Сообщения       |
| Создать   | /chat/create     | GET, POST | Создание чата   |
| Отправить | /chat/send/<id>  | POST      | Текст + файл    |
| Редактировать | /chat/edit/<id> | POST   | Только автор    |
| Удалить   | /chat/delete/<id>| POST      | Автор или admin |

Реал-тайм: Flask-SocketIO (connect, join, leave, send_message).
Шаблоны: `chat_list.html`, `chat_room.html`, `chat_create.html`.

---

## Роли и доступ

| Роль        | Доступ                                              |
|-------------|-----------------------------------------------------|
| admin       | Все модули: клиенты, заявки, фото, чат, карта,     |
|             | оборудование, пользователи, regulations, исполнители |
| engineer,   | Заявки (свои), фото, карта, чат                     |
| master      |                                                     |

Вход только через auth.

---

## Стек технологий

| Категория   | Технологии                                      |
|-------------|--------------------------------------------------|
| Backend     | Python 3.10+, Flask                             |
| БД          | PostgreSQL, SQLAlchemy, Flask-Migrate (Alembic) |
| Аутентификация | Flask-Login, Flask-JWT-Extended              |
| Реальное время | Flask-SocketIO                              |
| Дополнительно | Flask-WTF, Flask-CORS, Flask-Limiter, paginate |
| НЛП (русский) | spaCy (ru_core_news_sm), pymorphy3           |
| Документы   | python-docx, reportlab, openpyxl               |
| Интеграции  | Telegram (python-telegram-bot), Yandex API      |
| Продакшен   | Gunicorn                                        |

---

## Структура проекта

```
UtilBase/
├── app/
│   ├── __init__.py      # create_app(), blueprints
│   ├── config.py
│   ├── extensions.py
│   ├── blueprints/      # auth, clients, requests, photos, equipment,
│   │                   # map, workers, regulations, chat
│   ├── models/
│   ├── utils/           # pdf_generator, logger, check_overdue
│   └── templates/
├── static/
│   ├── css/
│   ├── images/
│   ├── manifest.json    # PWA
│   └── sw.js            # Service Worker
├── migrations/
├── docs/
├── run.py
├── requirements.txt
├── .env.example
├── install.bat          # Установка после клонирования
└── start run.bat        # Запуск + открытие браузера
```

---

## Лицензия

Условия указаны в репозитории.
"# UtilBase" 
