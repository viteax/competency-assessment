"""Пароли (scrypt из стандартной библиотеки) и JWT-токены доступа."""

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.config import settings

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, salt_b64, digest_b64 = password_hash.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), **_SCRYPT)
    return hmac.compare_digest(digest, base64.b64decode(digest_b64))


def create_access_token(user_id: int, token_version: int) -> str:
    """Токен сессии. Живёт session_idle_minutes и продлевается при активности."""
    expires = datetime.now(UTC) + timedelta(minutes=settings.session_idle_minutes)
    payload = {"sub": str(user_id), "ver": token_version, "typ": "session", "exp": expires}
    return jwt.encode(payload, settings.secret_key, _ALGORITHM)


@dataclass
class SessionToken:
    user_id: int
    token_version: int
    expires: datetime


def decode_access_token(token: str) -> SessionToken | None:
    """Разбирает токен сессии; None — если он подделан, истёк или это токен другого типа."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
        if payload.get("typ") != "session":
            return None
        return SessionToken(
            int(payload["sub"]), int(payload["ver"]), datetime.fromtimestamp(payload["exp"], UTC)
        )
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


DEVICE_TOKEN_DAYS = 180


def create_device_token(username: str) -> str:
    """Отметка «с этого браузера пользователь уже успешно входил» — такие попытки входа
    не замедляются защитой от подбора (её нельзя использовать, чтобы закрыть вход владельцу)."""
    expires = datetime.now(UTC) + timedelta(days=DEVICE_TOKEN_DAYS)
    payload = {"sub": username, "typ": "device", "exp": expires}
    return jwt.encode(payload, settings.secret_key, _ALGORITHM)


def device_token_username(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub") if payload.get("typ") == "device" else None
