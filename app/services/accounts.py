"""Учётные записи студентов: логины и пароли, которые раздают на листочке."""

import re
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.security import hash_password

# Без похожих символов (0/O, 1/l/I), чтобы пароль было легко переписать с листа.
_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

_RU = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
_LAT = (
    "a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p",
    "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya",
)  # fmt: skip
_TRANSLIT = str.maketrans(dict(zip(_RU, _LAT, strict=True)))


def generate_password(length: int = 10) -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


def username_base(login: str | None, email: str | None, full_name: str) -> str:
    """Логин из СДО, иначе часть e-mail до @, иначе фамилия и инициалы транслитом."""
    if login:
        return login
    if email:
        return email.split("@")[0]
    parts = full_name.lower().split()
    surname = parts[0].translate(_TRANSLIT) if parts else "student"
    initials = "".join(p[0].translate(_TRANSLIT) for p in parts[1:3])
    return f"{surname}.{initials}" if initials else surname


def unique_username(session: Session, base: str, taken: set[str]) -> str:
    """Свободный логин: base, base2, base3… `taken` — уже выданные в этой операции."""
    base = re.sub(r"[^a-z0-9._-]", "", base.lower())[:48] or "student"
    candidate, n = base, 1
    while candidate in taken or session.scalar(
        select(models.User.id).where(models.User.username == candidate)
    ):
        n += 1
        candidate = f"{base}{n}"
    taken.add(candidate)
    return candidate


def create_student_account(
    session: Session, student: models.Student, base: str, taken: set[str]
) -> tuple[str, str]:
    """Создаёт учётку студента и возвращает (логин, пароль) — пароль больше нигде не хранится."""
    username = unique_username(session, base, taken)
    password = generate_password()
    session.add(
        models.User(
            username=username,
            password_hash=hash_password(password),
            role=models.Role.STUDENT,
            student_id=student.id,
        )
    )
    return username, password
