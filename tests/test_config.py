import pytest
from pydantic import ValidationError

from app.config import Settings
from app.security import hash_password
from app.services.auth import demo_passwords_in_use


@pytest.fixture
def clean_env(monkeypatch):
    for name in ("ENVIRONMENT", "SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_prod_is_the_default_and_needs_a_secret(clean_env):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None)


def test_prod_rejects_short_secret(clean_env):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None, secret_key="short")


def test_prod_with_strong_secret(clean_env):
    assert Settings(_env_file=None, secret_key="x" * 40).is_prod


def test_dev_without_secret_gets_random_key(clean_env):
    with pytest.warns(UserWarning, match="временный ключ"):
        first = Settings(_env_file=None, environment="dev")
    with pytest.warns(UserWarning):
        second = Settings(_env_file=None, environment="dev")
    # Публичного ключа по умолчанию нет: каждый процесс получает свой случайный.
    assert first.secret_key != second.secret_key and len(first.secret_key) >= 32


def test_seed_refuses_in_prod(monkeypatch):
    from scripts import seed

    monkeypatch.setattr(seed.settings, "environment", "prod")
    with pytest.raises(SystemExit, match="prod"):
        seed.main()


def test_demo_passwords_detected(session):
    # После seed у всех демо-учёток публичные пароли — prod с такой базой не стартует.
    assert demo_passwords_in_use(session) == [
        "admin",
        "teacher",
        "student1",
        "student2",
        "student3",
    ]
    from app import models

    admin = session.query(models.User).filter_by(username="admin").one()
    admin.password_hash = hash_password("a-real-strong-password")
    session.commit()
    assert "admin" not in demo_passwords_in_use(session)


def test_prod_refuses_to_start_with_demo_passwords(session, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    import app.main as main

    monkeypatch.setattr(main.settings, "environment", "prod")
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=session.get_bind()))
    with pytest.raises(RuntimeError, match="admin, teacher, student1"):
        with TestClient(main.app):
            pass
