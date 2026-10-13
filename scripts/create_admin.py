"""Создаёт учётную запись администратора.

    python -m scripts.create_admin admin
Пароль спрашивается интерактивно или берётся из ADMIN_PASSWORD.
"""

import argparse
import getpass
import os

from sqlalchemy import select

from app import models
from app.db import SessionLocal
from app.errors import DomainError
from app.security import hash_password
from app.services.auth import validate_new_password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    args = parser.parse_args()
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Пароль: ")
    try:
        validate_new_password(password, args.username)
    except DomainError as exc:
        raise SystemExit(exc.detail) from None

    with SessionLocal() as session:
        if session.scalar(select(models.User).where(models.User.username == args.username)):
            raise SystemExit(f"пользователь {args.username} уже существует")
        session.add(
            models.User(
                username=args.username,
                password_hash=hash_password(password),
                role=models.Role.ADMIN,
            )
        )
        session.commit()
    print(f"администратор {args.username} создан")


if __name__ == "__main__":
    main()
