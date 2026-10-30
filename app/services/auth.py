"""Вход, пароли и защита от перебора."""

import math
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.demo import demo_credentials
from app.errors import Conflict, DomainError, TooManyRequests, Unauthorized
from app.security import hash_password, verify_password
from app.services.accounts import (
    generate_password,
    login_key,
    teacher_login,
    unique_teacher_login,
)
from app.services.common import name_key
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
            "этот пароль слишком распространён – его подберут первым, придумайте другой"
        )


def _aware(moment: datetime) -> datetime:
    # SQLite возвращает время без часового пояса; храним всегда в UTC.
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def throttle(session: Session, username: str, ip: str, trusted_device: bool = False) -> None:
    """Защита от подбора пароля, рассчитанная на вуз, где все выходят в интернет с одного IP.

    Жёсткой блокировки нет: после нескольких неудач по логину попытки разрешены не чаще раза
    в login_slowdown_seconds – подобрать так пароль нереально, а владелец обычно просто
    ждёт полминуты. С устройства, где владелец уже входил, замедления нет вовсе. Потолок
    на IP очень высокий и нужен только против массового перебора по многим логинам.

    Ограничение: чужому входу всё же можно помешать. Логин студента – его ФИО, и тот, кто
    раз в login_slowdown_seconds подставляет неверный пароль, каждый раз продлевает паузу;
    владелец с нового устройства (куки `device` ещё нет) почти не попадает в окно. Как
    снять паузу вручную – docs/deploy.md, раздел «Решение проблем».
    """
    now = models.utcnow()
    since = now - timedelta(minutes=settings.login_window_minutes)
    recent = select(models.LoginFailure).where(models.LoginFailure.created_at >= since)

    by_ip = session.scalar(
        select(func.count()).select_from(recent.where(models.LoginFailure.ip == ip).subquery())
    )
    if by_ip >= settings.login_max_failures_per_ip:
        raise TooManyRequests(
            "слишком много неудачных попыток входа с этого адреса – попробуйте позже",
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
            f"несколько неверных паролей подряд – следующая попытка через {seconds} с",
            headers={"Retry-After": str(seconds)},
        )


def authenticate(
    session: Session, username: str, password: str, ip: str, trusted_device: bool = False
) -> models.User:
    """Проверяет логин и пароль с учётом защиты от подбора (см. throttle)."""
    # Студент входит по ФИО в любом написании (find_user), поэтому и неудачи считаем по
    # нормализованному ключу – иначе «Иванов Иван» и «иванов  иван» были бы разными счётчиками.
    key = " ".join(username.casefold().replace("ё", "е").split())[:64]
    user = find_user(session, username)
    # У преподавателя написаний логина ещё больше: счётчик по ключу самой учётки.
    if user is not None and user.role == models.Role.TEACHER:
        key = login_key(user.username)[:64]
    throttle(session, key, ip, trusted_device)
    if not verify_password(password, user.password_hash if user else _DUMMY_HASH) or user is None:
        record_failure(session, key, ip)
        raise Unauthorized("неверный логин или пароль")
    session.execute(delete(models.LoginFailure).where(models.LoginFailure.username == key))
    session.commit()
    return user


def record_failure(session: Session, username: str, ip: str) -> None:
    session.add(models.LoginFailure(username=username[:64], ip=ip))
    # Заодно чистим записи старше окна – таблица не растёт бесконечно.
    horizon = models.utcnow() - timedelta(minutes=settings.login_window_minutes)
    session.execute(delete(models.LoginFailure).where(models.LoginFailure.created_at < horizon))
    session.commit()


def find_user(session: Session, login: str) -> models.User | None:
    """Учётка по логину. Студенты входят по ФИО – его сравниваем без учёта регистра, «ё/е»
    и лишних пробелов (в Python: lower() в SQLite не работает с кириллицей)."""
    user = session.scalar(select(models.User).where(models.User.username == login))
    if user is not None or " " not in login.strip():
        return user
    key = " ".join(login.casefold().replace("ё", "е").split())
    candidates = session.scalars(select(models.User).where(models.User.role == models.Role.STUDENT))
    student = next(
        (u for u in candidates if " ".join(u.username.casefold().replace("ё", "е").split()) == key),
        None,
    )
    if student is not None:
        return student
    # Преподаватели входят по фамилии и инициалам: точки и пробелы в них пишут по-разному.
    key = login_key(login)
    teachers = session.scalars(select(models.User).where(models.User.role == models.Role.TEACHER))
    matches = [u for u in teachers if login_key(u.username) == key]
    return matches[0] if len(matches) == 1 else None  # из нескольких не угадываем


def ensure_new_staff_name(session: Session, full_name: str) -> None:
    """Вторая учётка преподавателя с тем же ФИО – почти всегда случайный дубль: за ним
    закрепили бы часть дисциплин, и квоты разошлись бы по двум учёткам."""
    key = name_key(full_name)
    staff = session.scalars(
        select(models.User).where(
            models.User.role != models.Role.STUDENT, models.User.full_name.is_not(None)
        )
    )
    same = next((u for u in staff if name_key(u.full_name) == key), None)
    if same is not None:
        raise Conflict(f"учётная запись «{same.full_name}» уже есть (логин {same.username})")


def create_teachers(session: Session, full_names: list[str]) -> schemas.TeachersResult:
    """Учётки по списку ФИО; логин – из фамилии и инициалов. Пароль показывается один раз и
    нужно сменить его при первом входе. Строка с ошибкой пропускается, остальные создаются."""
    result = schemas.TeachersResult()
    taken: set[str] = set()
    for name in filter(None, (" ".join(n.split()) for n in full_names)):
        if not 3 <= len(teacher_login(name)) <= 64 or len(name) > 255:
            result.skipped.append(
                schemas.TeacherSkipped(full_name=name, reason="слишком короткое или длинное ФИО")
            )
            continue
        try:
            ensure_new_staff_name(session, name)
        except Conflict as e:
            result.skipped.append(schemas.TeacherSkipped(full_name=name, reason=str(e)))
            continue
        username = unique_teacher_login(session, name, taken)
        password = generate_password()
        session.add(
            models.User(
                username=username,
                full_name=name,
                password_hash=hash_password(password),
                role=models.Role.TEACHER,
                must_change_password=True,
            )
        )
        session.flush()  # следующая строка списка должна видеть эту учётку
        result.created.append(
            schemas.TeacherCreated(full_name=name, username=username, password=password)
        )
    session.commit()
    return result


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
