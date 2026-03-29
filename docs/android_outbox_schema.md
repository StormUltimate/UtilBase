# Android Outbox Schema (v1)

Документ описывает минимальную offline-first схему для Android клиента (Room + WorkManager) под текущее API ядра.

## 1) Room таблицы

## requests_cache

Кеш списка заявок для экрана “Мои/Просроченные/История”.

Поля (пример):

- `request_id` (PK, Long)
- `request_number` (String)
- `status` (String)
- `mode` (String)
- `planned_date` (String?)
- `address` (String?)
- `full_name` (String?)
- `phone` (String?)
- `is_dirty` (Boolean, default false) — есть несинхронизированные изменения
- `updated_at_local` (Long, epoch ms)

## request_details_cache

Кеш карточки заявки.

- `request_id` (PK, Long)
- `payload_json` (String) — JSON ответа `GET /requests/{id}`
- `updated_at_local` (Long)

## outbox_queue

Очередь JSON-операций.

- `id` (PK, Long, auto)
- `request_id` (Long, index)
- `operation_type` (String)
  Значения: `take`, `mode`, `close`, `item_add`, `item_update`, `item_delete`, `payment_add`, `chat_message`, `checklist_submit`
- `endpoint` (String) — путь API (`/requests/123/mode`)
- `method` (String) — `POST|PATCH|DELETE`
- `payload_json` (String) — body
- `client_operation_id` (String, UUID, unique)
- `depends_on_id` (Long?) — простая зависимость для последовательности
- `state` (String) — `pending|in_flight|sent|failed|blocked`
- `attempt_count` (Int)
- `next_retry_at` (Long?)
- `last_error_code` (String?)
- `last_error_message` (String?)
- `created_at` (Long)
- `updated_at` (Long)

Рекомендуемые индексы:

- `(state, next_retry_at)`
- `(request_id, created_at)`
- `client_operation_id UNIQUE`

## media_upload_queue

Очередь медиа-операций (multipart).

- `id` (PK, Long, auto)
- `request_id` (Long, index)
- `local_uri` (String) — `content://...` или file-path
- `mime_type` (String)
- `size_bytes` (Long?)
- `client_operation_id` (String, UUID, unique)
- `state` (String) — `pending|in_flight|sent|failed`
- `attempt_count` (Int)
- `next_retry_at` (Long?)
- `last_error_code` (String?)
- `last_error_message` (String?)
- `created_at` (Long)
- `updated_at` (Long)

## 2) Порядок синхронизации

При `NetworkType.CONNECTED`:

1. flush `outbox_queue` со статусными операциями (`take`, `mode`, `close`);
2. flush `outbox_queue` с финансовыми/чат/чек-лист (`items`, `payments`, `chat`, `checklist`);
3. flush `media_upload_queue`.

Внутри очереди — строгий порядок `created_at ASC`.

## 3) Worker'ы

Минимум 3 worker’а:

- `OutboxStatusWorker`
- `OutboxDataWorker`
- `MediaUploadWorker`

Каждый запускается через `WorkManager`:

- constraint: `NetworkType.CONNECTED`
- backoff: `EXPONENTIAL`
- уникальная работа: `ExistingWorkPolicy.KEEP` (или `APPEND_OR_REPLACE` для цепочки)

## 4) Идемпотентность

Каждая операция получает `client_operation_id` (UUID), который отправляется:

- в body `client_operation_id`, или
- в `X-Client-Operation-Id`.

Если запрос был доставлен, но ответ потерян, повтор с тем же UUID должен быть безопасным.

## 5) Локальный optimistic UI

- После локального действия UI обновляется сразу.
- В `requests_cache.is_dirty=true`.
- После успешной синхронизации: `is_dirty=false`.

Состояние для UI:

- `Ожидает отправки` (`pending`)
- `Отправлено` (`sent`)
- `Ошибка` (`failed`)

## 6) Conflict handling

Если сервер вернул `conflict_fsm`:

- пометить запись как `failed`;
- не повторять автоматически;
- показать пользователю действие “Обновить заявку” / “Повторить после исправления”.

Если `401 unauthorized`:

- выполнить refresh токена;
- повторить операцию 1 раз.

Если `5xx`/timeout/network:

- увеличивать `attempt_count`;
- считать `next_retry_at` по exponential backoff;
- оставлять запись `pending`.
