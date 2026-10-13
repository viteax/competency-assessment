from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-secret-change-me-in-production!"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # dev — локальная разработка и демо; prod — реальная эксплуатация (строже проверки,
    # cookie только по HTTPS, демо-данные запрещены).
    environment: Literal["dev", "prod"] = "dev"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/competency"
    # Доля правильных ответов, начиная с которой компетенция считается сформированной.
    mastery_threshold: float = 0.6

    # В проде обязателен свой случайный ключ, например:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    secret_key: str = DEV_SECRET_KEY
    access_token_ttl_minutes: int = 12 * 60

    # Защита от перебора паролей: столько неудачных попыток входа за окно — и пауза.
    login_max_failures: int = 5
    login_max_failures_per_ip: int = 30
    login_window_minutes: int = 15

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"

    @model_validator(mode="after")
    def strong_secret_in_prod(self) -> "Settings":
        if self.is_prod and (self.secret_key == DEV_SECRET_KEY or len(self.secret_key) < 32):
            raise ValueError("в ENVIRONMENT=prod нужен свой SECRET_KEY длиной от 32 символов")
        return self


settings = Settings()
