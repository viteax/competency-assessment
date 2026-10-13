"""Вход, пароли и защита от перебора."""

from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.errors import DomainError, TooManyRequests, Unauthorized
from app.security import hash_password, verify_password
from app.services.accounts import generate_password

MIN_PASSWORD_LENGTH = 8


def validate_new_password(password: str, username: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise DomainError(f"пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")
    if password.casefold() == username.casefold():
        raise DomainError("пароль не должен совпадать с логином")


def _check_rate_limit(session: Session, username: str, ip: str) -> None:
    since = models.utcnow() - timedelta(minutes=settings.login_window_minutes)
    failures = (
        select(func.count())
        .select_from(models.LoginFailure)
        .where(models.LoginFailure.created_at >= since)
    )
    by_user = session.scalar(
        failures.where(models.LoginFailure.username == username, models.LoginFailure.ip == ip)
    )
    by_ip = session.scalar(failures.where(models.LoginFailure.ip == ip))
    if by_user >= settings.login_max_failures or by_ip >= settings.login_max_failures_per_ip:
        minutes = settings.login_window_minutes
        raise TooManyRequests(
            f"слишком много неудачных попыток входа — попробуйте через {minutes} мин.",
            headers={"Retry-After": str(minutes * 60)},
        )


def authenticate(session: Session, username: str, password: str, ip: str) -> models.User:
    """Проверяет логин и пароль. Неудачные попытки считаются по паре логин+IP и по IP,
    чтобы перебор нельзя было ни вести с одного адреса, ни заблокировать им чужую учётку
    навсегда."""
    _check_rate_limit(session, username, ip)
    user = session.scalar(select(models.User).where(models.User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        session.add(models.LoginFailure(username=username[:64], ip=ip))
        # Заодно чистим записи старше окна — таблица не растёт бесконечно.
        horizon = models.utcnow() - timedelta(minutes=settings.login_window_minutes)
        session.execute(delete(models.LoginFailure).where(models.LoginFailure.created_at < horizon))
        session.commit()
        raise Unauthorized("неверный логин или пароль")
    session.execute(
        delete(models.LoginFailure).where(
            models.LoginFailure.username == username, models.LoginFailure.ip == ip
        )
    )
    session.commit()
    return user


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
