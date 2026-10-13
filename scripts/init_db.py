"""Создаёт таблицы в БД из DATABASE_URL. Пока нет миграций — достаточно для MVP."""

from app import models  # noqa: F401  регистрирует модели в metadata
from app.db import Base, engine


def main() -> None:
    Base.metadata.create_all(engine)
    print("таблицы созданы")


if __name__ == "__main__":
    main()
