"""Применяет миграции Alembic к БД из DATABASE_URL (то же, что `alembic upgrade head`)."""

from pathlib import Path

from alembic import command
from alembic.config import Config

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def migrate() -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


if __name__ == "__main__":
    migrate()
