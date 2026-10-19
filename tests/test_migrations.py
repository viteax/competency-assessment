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


def test_single_choice_questions_become_open(tmp_path):
    """Вопрос «выбор одного ответа» превращается в открытый: правильный вариант – принимаемый
    ответ; ответ студента сохраняется текстом, оценка не меняется."""
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    config = Config(str(ALEMBIC_INI))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "7d52f53d0ca7")
        for statement in (
            "INSERT INTO competency (id, code, kind, description) VALUES (1, 'ПК-1', 'ПК', 'к')",
            "INSERT INTO question (id, competency_id, text, kind, difficulty) "
            "VALUES (1, 1, 'Стандартный порт SSH', 'single', 'basic')",
            "INSERT INTO answer_option (id, question_id, text, is_correct, position) VALUES "
            "(1, 1, '22', 1, 0), (2, 1, '21', 0, 1), (3, 1, '80', 0, 2)",
            "INSERT INTO attempt_answer (attempt_id, question_id, option_id, is_correct) "
            "VALUES (1, 1, 2, 0)",
        ):
            connection.exec_driver_sql(statement)

        command.upgrade(config, "head")
        sql = connection.exec_driver_sql
        assert sql("SELECT kind FROM question").scalar() == "open"
        assert sql("SELECT text FROM answer_option").scalars().all() == ["22"]
        assert sql("SELECT response, is_correct FROM attempt_answer").one() == ('{"text": "21"}', 0)
