from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app
from scripts.seed import seed


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
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
    return TestClient(app)
