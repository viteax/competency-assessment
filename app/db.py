from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def enforce_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite по умолчанию не проверяет внешние ключи – без этого удаление записи, на которую
    ссылаются, проходит молча и оставляет «висячие» ссылки (PostgreSQL проверяет всегда)."""
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))


engine = create_engine(settings.database_url)
enforce_sqlite_foreign_keys(engine)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
