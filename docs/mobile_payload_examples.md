# Mobile Payload Examples (v1)

Ниже примеры тел запросов для Android клиента.
`<id>` и токены замените на реальные значения.

## Auth

## POST /api/v1/auth/login

```json
{
  "username": "master1",
  "password": "secret"
}
```

## POST /api/v1/auth/refresh

Без тела, с refresh JWT в `Authorization: Bearer <refresh_token>`.

## POST /api/v1/auth/logout

```json
{
  "refresh_token": "<refresh_token>"
}
```

## Requests

## POST /api/v1/requests/<id>/take

```json
{
  "client_operation_id": "7a10ef39-530e-4e5c-bb20-2bc1f365db0d"
}
```

## POST /api/v1/requests/<id>/mode

```json
{
  "mode": "on_way",
  "client_operation_id": "0bd74988-a53c-4a18-8d74-6d2f7ea6f143"
}
```

```json
{
  "mode": "in_progress",
  "client_operation_id": "87c7b6a9-0a13-48d8-9d2f-6784ca95df67"
}
```

```json
{
  "mode": "completed",
  "client_operation_id": "c6edcf82-eb10-4922-8d42-860b2fba6aa3"
}
```

## POST /api/v1/requests/<id>/close

```json
{
  "client_operation_id": "7fef1d84-4bfe-4f23-8dff-f7684966cf8f"
}
```

## Checklist

## POST /api/v1/requests/<id>/checklist-submit

```json
{
  "items": [
    {
      "item_id": 101,
      "checked": true
    },
    {
      "item_id": 102,
      "value_text": "Давление в норме"
    },
    {
      "item_id": 103,
      "value_number": 12.5
    }
  ]
}
```

Если ответ на пункт связан с фото:

```json
{
  "items": [
    {
      "item_id": 104,
      "checked": true,
      "media_id": 9988
    }
  ]
}
```

## Items

## POST /api/v1/requests/<id>/items

```json
{
  "item_type": "material",
  "name": "Фильтр тонкой очистки",
  "quantity": 2,
  "unit_price": 450.0,
  "source": "master_recommended",
  "comment": "Замена по износу",
  "client_operation_id": "7336a4d3-f9db-40d7-b25b-11e06f0b6a03"
}
```

## PATCH /api/v1/requests/<id>/items/<itemId>

```json
{
  "quantity": 3,
  "unit_price": 430.0,
  "client_operation_id": "5efeb208-f8a8-4b2f-b20e-d37a4e7bcfb2"
}
```

## DELETE /api/v1/requests/<id>/items/<itemId>

Без тела, но добавляйте `X-Client-Operation-Id: <uuid>`.

## Payments

## POST /api/v1/requests/<id>/payments

```json
{
  "amount": 3500.0,
  "payment_method": "cash",
  "is_cash": true,
  "note": "Оплачено на месте",
  "client_operation_id": "3f5e9338-abdb-4ba6-a15f-95e2cf3f61d2"
}
```

## Chat

## POST /api/v1/requests/<id>/chat/messages

```json
{
  "message_text": "На объекте, начинаю диагностику",
  "client_operation_id": "6b65ef9b-f526-41f4-9448-c3ec4ff9a0f4"
}
```

## Media (multipart)

## POST /api/v1/requests/<id>/media

`Content-Type: multipart/form-data`:

- `file`: binary
- `client_operation_id`: UUID

Пример заголовка:

- `X-Client-Operation-Id: 1f2ef201-0d54-454f-8383-1db2e44e7765`

## Ошибки, которые надо обрабатывать в UI

- `conflict_fsm` — показать понятный текст и предложить обновить карточку.
- `validation_error` — подсветить некорректное поле.
- `forbidden` — нет доступа к заявке/действию.
- `invalid_state` — действие уже неактуально.
- `unauthorized` — обновить токен и повторить 1 раз.
