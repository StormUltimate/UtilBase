"""Обработчики ошибок и загрузка пользователя для Flask-JWT-Extended."""


def register_jwt_handlers(jwt_manager):
    from app.models.all_models import Users

    @jwt_manager.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_payload):
        uid = jwt_payload.get("sub")
        if uid is None:
            return None
        try:
            return Users.query.get(int(uid))
        except (TypeError, ValueError):
            return None

    @jwt_manager.expired_token_loader
    def expired_token_callback(_jwt_header, jwt_payload):
        from flask import jsonify

        return (
            jsonify(
                {
                    "error": {
                        "code": "token_expired",
                        "message": "Срок действия токена истёк",
                    }
                }
            ),
            401,
        )

    @jwt_manager.invalid_token_loader
    def invalid_token_callback(reason):
        from flask import jsonify

        return (
            jsonify(
                {
                    "error": {
                        "code": "invalid_token",
                        "message": str(reason) if reason else "Недействительный токен",
                    }
                }
            ),
            401,
        )

    @jwt_manager.unauthorized_loader
    def unauthorized_callback(reason):
        from flask import jsonify

        return (
            jsonify(
                {
                    "error": {
                        "code": "unauthorized",
                        "message": (reason or "Требуется авторизация"),
                    }
                }
            ),
            401,
        )
