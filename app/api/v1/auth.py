"""JWT: вход, обновление, выход, текущий пользователь."""

from datetime import datetime

from flask import current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    current_user,
    decode_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from werkzeug.security import check_password_hash

from app.api.v1 import api_v1_bp
from app.extensions import db
from app.models.all_models import RefreshToken, Users


def _api_error(code: str, message: str, http_status: int):
    return jsonify({"error": {"code": code, "message": message}}), http_status


def _strip_bearer(raw: str | None) -> str | None:
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return raw


def _store_refresh_jti(user_id: int, refresh_token_str: str) -> None:
    decoded = decode_token(refresh_token_str)
    jti = decoded.get("jti")
    if not jti:
        raise ValueError("refresh token без jti")
    exp_ts = decoded.get("exp")
    expires_at = datetime.utcfromtimestamp(exp_ts) if exp_ts else datetime.utcnow()
    row = RefreshToken(
        user_id=user_id,
        jti=jti,
        expires_at=expires_at,
    )
    db.session.add(row)


@api_v1_bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return _api_error("validation_error", "Укажите username и password", 400)

    user = Users.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return _api_error("invalid_credentials", "Неверное имя пользователя или пароль", 401)

    identity = str(user.id)
    access = create_access_token(identity=identity)
    refresh = create_refresh_token(identity=identity)
    try:
        _store_refresh_jti(user.id, refresh)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _api_error("server_error", "Не удалось выдать токен", 500)

    expires_in = int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds())
    return (
        jsonify(
            {
                "access_token": access,
                "refresh_token": refresh,
                "token_type": "Bearer",
                "expires_in": expires_in,
            }
        ),
        200,
    )


@api_v1_bp.route("/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user_id = int(get_jwt_identity())
    claims = get_jwt()
    old_jti = claims.get("jti")
    if not old_jti:
        return _api_error("invalid_token", "Нет jti в refresh-токене", 401)

    row = RefreshToken.query.filter_by(jti=old_jti, user_id=user_id).first()
    if not row or row.revoked_at is not None:
        return _api_error("invalid_token", "Refresh-токен отозван или неизвестен", 401)
    if row.expires_at < datetime.utcnow():
        return _api_error("token_expired", "Срок действия refresh-токена истёк", 401)

    identity = str(user_id)
    new_access = create_access_token(identity=identity)
    new_refresh = create_refresh_token(identity=identity)

    row.revoked_at = datetime.utcnow()
    try:
        _store_refresh_jti(user_id, new_refresh)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _api_error("server_error", "Не удалось обновить токен", 500)

    expires_in = int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds())
    return jsonify(
        {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "Bearer",
            "expires_in": expires_in,
        }
    )


@api_v1_bp.route("/auth/logout", methods=["POST"])
def logout():
    """Отзыв refresh-токена (передавайте его в теле как refresh_token или Authorization: Bearer <refresh>)."""
    data = request.get_json(silent=True) or {}
    raw = data.get("refresh_token") or request.headers.get("Authorization")
    token = _strip_bearer(raw)
    if not token:
        return _api_error(
            "validation_error", "Передайте refresh_token в JSON или Authorization", 400
        )

    try:
        decoded = decode_token(token)
    except Exception:
        return _api_error("invalid_token", "Недействительный refresh-токен", 401)

    if decoded.get("type") != "refresh":
        return _api_error("validation_error", "Ожидается refresh-токен", 400)

    jti = decoded.get("jti")
    if not jti:
        return _api_error("invalid_token", "Нет jti", 401)

    row = RefreshToken.query.filter_by(jti=jti).first()
    if row and row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        db.session.commit()

    return jsonify({"ok": True}), 200


@api_v1_bp.route("/auth/me", methods=["GET"])
@jwt_required()
def me():
    if not current_user:
        return _api_error("unauthorized", "Пользователь не найден", 401)
    from app.api.v1.helpers import resolve_worker_id

    wid = resolve_worker_id(current_user)
    return (
        jsonify(
            {
                "id": current_user.id,
                "username": current_user.username,
                "role": current_user.role,
                "worker_id": current_user.worker_id,
                "resolved_worker_id": wid,
            }
        ),
        200,
    )
