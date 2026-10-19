import os
from collections.abc import Callable, Iterator

# До импорта приложения: по умолчанию включён строгий режим prod.
os.environ["ENVIRONMENT"] = "dev"
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-123")

# ruff: noqa: E402

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, enforce_sqlite_foreign_keys, get_session
from app.main import app
from scripts.seed import ADMIN_LOGIN, STUDENT_PASSWORD, seed


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    enforce_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        seed(s)

    def override() -> Iterator[Session]:
        with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override
    with factory() as s:
        yield s
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def client(session: Session) -> TestClient:
    """Клиент без авторизации."""
    return TestClient(app)


@pytest.fixture
def login(session: Session) -> Callable[[str, str], TestClient]:
    """Возвращает клиент, авторизованный под указанным пользователем."""

    def _login(username: str, password: str) -> TestClient:
        c = TestClient(app)
        response = c.post("/auth/token", data={"username": username, "password": password})
        assert response.status_code == 200, response.text
        c.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
        return c

    return _login


@pytest.fixture
def admin(login) -> TestClient:
    return login(*ADMIN_LOGIN)


@pytest.fixture
def student(login) -> TestClient:
    """student1 – Иванов Иван Иванович из группы ПИ-21."""
    return login("student1", STUDENT_PASSWORD)
