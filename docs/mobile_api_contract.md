# Mobile API Contract (v1)

Документ фиксирует минимальный контракт между Android и backend `UtilBase` для сценария исполнителя.

## 1) База

- Base URL: `https://<host>/api/v1`
- Auth: `Authorization: Bearer <access_token>`
- Формат времени: ISO-8601 (`2026-03-24T10:30:00Z`)
- Формат ошибок:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Укажите mode"
  }
}
```

## 2) Auth

- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

Токены:

- access token: короткий TTL.
- refresh token: длинный TTL, ротация и отзыв поддерживаются на сервере.

## 3) Заявки и FSM

Основные endpoint'ы исполнителя:

- `GET /requests`
- `GET /requests/{id}`
- `POST /requests/{id}/take`
- `POST /requests/{id}/mode` (`on_way | in_progress | waiting | completed`)
- `POST /requests/{id}/close`

FSM (execution mode):

- `normal -> on_way -> in_progress -> completed`
- Допустим `in_progress <-> waiting`
- Нарушение перехода: `error.code=conflict_fsm`

## 4) Правила закрытия

Закрытие может быть отклонено с `409 conflict_fsm`, если:

- режим не `completed`;
- не выполнены обязательные пункты чек-листа;
- не добавлено минимальное число фото (`API_CLOSE_MIN_PHOTOS`).

## 5) Чек-лист

- `GET /requests/{id}/checklist-template`
- `POST /requests/{id}/checklist-submit`

Выбор шаблона:

1. Явно закрепленный в заявке;
2. По `equipment_id`;
3. `is_default=true`;
4. Любой активный (fallback от пустой базы).

## 6) Медиа, материалы, оплаты, чат

- Медиа: `POST /requests/{id}/media` (multipart, поле `file`)
- Материалы: `GET|POST|PATCH|DELETE /requests/{id}/items...`
- Оплаты: `GET|POST /requests/{id}/payments`
- Чат: `GET|POST /requests/{id}/chat/messages`

## 7) Offline-first и идемпотентность

Для mutation endpoint'ов обязательно передавать `client_operation_id` (UUID):

- JSON: `client_operation_id`
- multipart/form-data: `client_operation_id`
- header: `X-Client-Operation-Id`

Сервер хранит операции в `request_client_operations`.
Повтор того же `client_operation_id` не должен менять данные повторно.

### Рекомендуемый порядок отправки outbox

1. `take/mode/close` (статусные действия)
2. `items/payments`
3. `media` (тяжелые файлы)

### Retry policy (Android рекомендация)

- `5xx`, timeout, network I/O: retry с exponential backoff
- `409 conflict_fsm`, `400 validation_error`, `403 forbidden`: не retry автоматически
- `401 unauthorized`: обновить access через refresh и повторить 1 раз

## 8) Коды ошибок (минимум)

- `validation_error`
- `invalid_state`
- `conflict_fsm`
- `forbidden`
- `not_found`
- `unauthorized`
- `server_error`
- `https_required` (если включен `API_FORCE_HTTPS=true`)

## 9) HTTPS

В production включить `API_FORCE_HTTPS=true`.

- API по HTTP: `426 https_required`
- Web по HTTP: `301 -> https`
