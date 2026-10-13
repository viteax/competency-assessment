from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/competency"
    # Доля правильных ответов, начиная с которой компетенция считается сформированной.
    mastery_threshold: float = 0.6


settings = Settings()
