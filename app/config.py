import secrets
import warnings
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки из переменных окружения (или файла .env).

    По умолчанию – строгий режим prod: забытая настройка не должна оставлять систему открытой.
    Для разработки нужно явно указать ENVIRONMENT=dev.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # prod – реальная эксплуатация; dev – локальная разработка и демо (разрешены демо-данные,
    # cookie без флага Secure, ключ подписи можно не задавать).
    environment: Literal["dev", "prod"] = "prod"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/competency"
    # Доля правильных ответов, начиная с которой компетенция считается сформированной.
    mastery_threshold: float = 0.6

    # Ключ подписи токенов. В prod обязателен, например:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    # В dev без ключа генерируется случайный на время работы процесса – публичного ключа
    # по умолчанию нет, поэтому токен нельзя подделать, даже если забыть про настройку.
    secret_key: str | None = None
    log_level: str = "INFO"

    # Сессия завершается после стольких минут без действий (продлевается при активности).
    session_idle_minutes: int = 60

    # Защита от подбора паролей (см. services/auth.py).
    login_slowdown_after: int = 5  # неудачных попыток для логина – дальше пауза между попытками
    login_slowdown_seconds: int = 30
    login_max_failures_per_ip: int = 300  # потолок с одного адреса (кампус выходит с одного IP)
    login_window_minutes: int = 15
    # Регистрация: потолок неудачных попыток (ФИО нет в списке) с одного адреса за то же окно.
    # Как у входа, он высокий: кампус выходит с одного IP, и опечатки всех студентов вместе не
    # должны закрыть регистрацию вузу. Паузы нет – при массовой регистрации они неизбежны.
    registration_max_failures_per_ip: int = 300

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"

    @model_validator(mode="after")
    def check_secret(self) -> "Settings":
        if self.secret_key is None:
            if self.is_prod:
                raise ValueError(
                    "задайте SECRET_KEY (от 32 символов) или ENVIRONMENT=dev для разработки"
                )
            warnings.warn(
                "SECRET_KEY не задан: временный ключ, сессии сбросятся при перезапуске",
                stacklevel=2,
            )
            self.secret_key = secrets.token_urlsafe(48)
        elif self.is_prod and len(self.secret_key) < 32:
            raise ValueError("в ENVIRONMENT=prod SECRET_KEY должен быть не короче 32 символов")
        return self


settings = Settings()
