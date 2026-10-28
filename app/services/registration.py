"""Самостоятельная регистрация студента: сверка ФИО со списком группы, свой пароль.

Студент выбирает группу, вводит ФИО так, как оно записано в списке (регистр, «ё/е» и лишние
пробелы не важны), и задаёт пароль. Логин – ФИО (у однофамильцев с одинаковым ФИО – ФИО и
группа). Учётку можно завести один раз; администратор видит, когда она создана, и может
сбросить пароль.
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.errors import Conflict, NotFound, TooManyRequests
from app.security import hash_password
from app.services import auth
from app.services.common import get_or_404

_ALREADY = (
    "этот студент уже зарегистрирован. Если вы забыли пароль, обратитесь к "
    "преподавателю или администратору – он его сбросит"
)


def normalize_name(text: str) -> str:
    return " ".join(text.casefold().replace("ё", "е").split())


def find_student(session: Session, group: models.Group, full_name: str) -> models.Student:
    key = normalize_name(full_name)
    student = next((s for s in group.students if normalize_name(s.full_name) == key), None)
    if student is None:
        raise NotFound(
            f"студента «{' '.join(full_name.split())}» нет в списке группы {group.name}. "
            "Проверьте, как написано ФИО, или обратитесь к преподавателю"
        )
    return student


def _throttle(session: Session, attempt_key: str) -> None:
    """Потолок неудач с одного адреса: перебирать ФИО однокурсников можно лишь ограниченно.
    Паузы, как у входа, нет – кампус выходит с одного IP, и опечатки одних замедлили бы всех."""
    since = models.utcnow() - timedelta(minutes=settings.login_window_minutes)
    failures = session.scalar(
        select(func.count())
        .select_from(models.LoginFailure)
        .where(models.LoginFailure.username == attempt_key, models.LoginFailure.created_at >= since)
    )
    if failures >= settings.registration_max_failures_per_ip:
        raise TooManyRequests(
            "слишком много неудачных попыток регистрации с этого адреса – попробуйте позже",
            headers={"Retry-After": str(settings.login_window_minutes * 60)},
        )


def register_student(
    session: Session, group_id: int, full_name: str, password: str, ip: str
) -> models.User:
    attempt_key = f"регистрация {ip}"
    _throttle(session, attempt_key)
    group = get_or_404(session, models.Group, group_id)
    try:
        student = find_student(session, group, full_name)
    except NotFound:
        auth.record_failure(session, attempt_key, ip)
        raise
    if session.scalar(select(models.User.id).where(models.User.student_id == student.id)):
        raise Conflict(_ALREADY)
    username = student.full_name
    if session.scalar(select(models.User.id).where(models.User.username == username)):
        username = f"{student.full_name} ({group.name})"  # полный тёзка в другой группе
    auth.validate_new_password(password, username)
    user = models.User(
        username=username[:64],
        password_hash=hash_password(password),
        role=models.Role.STUDENT,
        student=student,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        # Двойной клик: учётку успел создать параллельный запрос – отвечаем как на повтор.
        session.rollback()
        raise Conflict(_ALREADY) from None
    return user
