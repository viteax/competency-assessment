"""Пароли (scrypt из стандартной библиотеки) и JWT-токены доступа."""

import base64
import hashlib
import hmac
import secrets
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
    expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {"sub": str(user_id), "ver": token_version, "exp": expires}
    return jwt.encode(payload, settings.secret_key, _ALGORITHM)


def decode_access_token(token: str) -> tuple[int, int] | None:
    """(id пользователя, версия токена) или None, если токен подделан или истёк."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
        return int(payload["sub"]), int(payload["ver"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
