"""Миграции Alembic применяются с нуля, откатываются и совпадают с моделями."""

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db import Base

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def test_migrations_match_models(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    config = Config(str(ALEMBIC_INI))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == [], f"модели разошлись с миграциями, нужна новая ревизия: {diff}"

        command.downgrade(config, "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
