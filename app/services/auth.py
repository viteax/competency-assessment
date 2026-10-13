"""Вход, пароли и защита от перебора."""

import math
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.demo import demo_credentials
from app.errors import DomainError, TooManyRequests, Unauthorized
from app.security import hash_password, verify_password
from app.services.accounts import generate_password
from app.services.common_passwords import is_common_password

MIN_PASSWORD_LENGTH = 8

# Хэш случайного пароля: для несуществующего логина всё равно считаем scrypt, чтобы по времени
# ответа нельзя было понять, есть такой логин или нет.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def validate_new_password(password: str, username: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise DomainError(f"пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")
    if username.casefold() in password.casefold():
        raise DomainError("пароль не должен содержать логин")
    if is_common_password(password):
        raise DomainError(
            "этот пароль слишком распространён — его подберут первым, придумайте другой"
        )


def _aware(moment: datetime) -> datetime:
    # SQLite возвращает время без часового пояса; храним всегда в UTC.
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _throttle(session: Session, username: str, ip: str, trusted_device: bool) -> None:
    """Защита от подбора пароля, рассчитанная на вуз, где все выходят в интернет с одного IP.

    Жёсткой блокировки нет — иначе студент мог бы закрыть вход одногруппнику или всему
    кампусу. Вместо этого после нескольких неудач по логину попытки разрешены не чаще раза
    в login_slowdown_seconds: подобрать так пароль нереально, а настоящий владелец просто
    ждёт полминуты. С устройства, где владелец уже входил, замедления нет вовсе. Потолок
    на IP очень высокий и нужен только против массового перебора по многим логинам.
    """
    now = models.utcnow()
    since = now - timedelta(minutes=settings.login_window_minutes)
    recent = select(models.LoginFailure).where(models.LoginFailure.created_at >= since)

    by_ip = session.scalar(
        select(func.count()).select_from(recent.where(models.LoginFailure.ip == ip).subquery())
    )
    if by_ip >= settings.login_max_failures_per_ip:
        raise TooManyRequests(
            "слишком много неудачных попыток входа с этого адреса — попробуйте позже",
            headers={"Retry-After": str(settings.login_window_minutes * 60)},
        )
    if trusted_device:
        return

    failures = session.scalars(
        recent.where(models.LoginFailure.username == username)
        .order_by(models.LoginFailure.created_at.desc())
        .limit(settings.login_slowdown_after)
    ).all()
    if len(failures) < settings.login_slowdown_after:
        return
    wait = settings.login_slowdown_seconds - (now - _aware(failures[0].created_at)).total_seconds()
    if wait > 0:
        seconds = math.ceil(wait)
        raise TooManyRequests(
            f"несколько неверных паролей подряд — следующая попытка через {seconds} с",
            headers={"Retry-After": str(seconds)},
        )


def authenticate(
    session: Session, username: str, password: str, ip: str, trusted_device: bool = False
) -> models.User:
    """Проверяет логин и пароль с учётом защиты от подбора (см. _throttle)."""
    _throttle(session, username, ip, trusted_device)
    user = session.scalar(select(models.User).where(models.User.username == username))
    if not verify_password(password, user.password_hash if user else _DUMMY_HASH) or user is None:
        session.add(models.LoginFailure(username=username[:64], ip=ip))
        # Заодно чистим записи старше окна — таблица не растёт бесконечно.
        horizon = models.utcnow() - timedelta(minutes=settings.login_window_minutes)
        session.execute(delete(models.LoginFailure).where(models.LoginFailure.created_at < horizon))
        session.commit()
        raise Unauthorized("неверный логин или пароль")
    session.execute(delete(models.LoginFailure).where(models.LoginFailure.username == username))
    session.commit()
    return user


def demo_passwords_in_use(session: Session) -> list[str]:
    """Логины демо-учёток, у которых всё ещё публичный пароль из README."""
    return [
        username
        for username, password in demo_credentials()
        if (user := session.scalar(select(models.User).where(models.User.username == username)))
        and verify_password(password, user.password_hash)
    ]


def _set_password(user: models.User, password: str, must_change: bool) -> None:
    user.password_hash = hash_password(password)
    user.must_change_password = must_change
    user.token_version += 1  # старые токены (на других устройствах) больше не действуют


def change_password(session: Session, user: models.User, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise DomainError("текущий пароль указан неверно")
    if current == new:
        raise DomainError("новый пароль должен отличаться от текущего")
    validate_new_password(new, user.username)
    _set_password(user, new, must_change=False)
    session.commit()


def reset_password(session: Session, user: models.User) -> str:
    """Выдаёт новый случайный пароль; при входе его потребуется сменить."""
    password = generate_password()
    _set_password(user, password, must_change=True)
    session.commit()
    return password
