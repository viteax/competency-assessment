import pytest
from pydantic import ValidationError

from app.config import DEV_SECRET_KEY, Settings


def test_dev_allows_default_secret():
    assert Settings(environment="dev").secret_key == DEV_SECRET_KEY


@pytest.mark.parametrize("secret", [DEV_SECRET_KEY, "short"])
def test_prod_requires_strong_secret(secret: str):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(environment="prod", secret_key=secret)


def test_prod_with_strong_secret():
    assert Settings(environment="prod", secret_key="x" * 40).is_prod


def test_seed_refuses_in_prod(monkeypatch):
    from scripts import seed

    monkeypatch.setattr(seed.settings, "environment", "prod")
    with pytest.raises(SystemExit, match="prod"):
        seed.main()
