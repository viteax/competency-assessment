"""Миграции Alembic применяются с нуля, откатываются и совпадают с моделями."""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

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


def _upgrade_with(tmp_path, statements: list[str]):
    """Данные на ревизии до направлений у справочников, затем обновление до последней."""
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    config = Config(str(ALEMBIC_INI))
    connection = engine.connect()
    config.attributes["connection"] = connection
    with connection.begin():
        command.upgrade(config, "f80e0e615d56")
        for statement in statements:
            connection.exec_driver_sql(statement)
        command.upgrade(config, "head")
    return connection


def test_catalogs_get_directions_from_curriculum(tmp_path):
    connection = _upgrade_with(
        tmp_path,
        [
            "INSERT INTO direction (id, code, name) VALUES "
            "(1, '09.03.01', 'ИВТ'), (2, '15.04.06', 'Мехатроника')",
            "INSERT INTO competency (id, code, kind, description) VALUES "
            "(1, 'ПК-1', 'ПК', 'п'), (2, 'ОПК-2', 'ОПК', 'о'), (3, 'УК-1', 'УК', 'у')",
            "INSERT INTO indicator (id, competency_id, code, description) "
            "VALUES (1, 1, 'ПК-1.1', 'и')",
            "INSERT INTO discipline (id, name) VALUES (1, 'Базы данных'), "
            "(2, 'Учебная практика'), (3, 'Философия'), (4, 'Сети')",
            "INSERT INTO discipline_competency VALUES (1, 1), (2, 2)",
            "INSERT INTO curriculum_entry (id, direction_id, discipline_id, first_semester, "
            "last_semester) VALUES (1, 2, 1, 1, 1), (2, 1, 2, 2, 2), (3, 2, 4, 3, 3)",
            "INSERT INTO prof_standard (id, code, name) VALUES (1, '06.001', 'Программист')",
            "INSERT INTO general_labor_function (id, standard_id, code, name, "
            "qualification_level) VALUES (1, 1, 'D', 'о', 6)",
            "INSERT INTO labor_function (id, general_function_id, code, name) "
            "VALUES (1, 1, 'D/01.6', 'т')",
            "INSERT INTO labor_function_competency VALUES (1, 1)",
            "INSERT INTO question (id, competency_id, discipline_id, text, kind, difficulty) "
            "VALUES (1, 1, 1, 'в', 'open', 'basic')",
        ],
    )
    sql = connection.exec_driver_sql
    # Дисциплина – в направлении своей строки плана, без плана – в основном (больше строк).
    assert sql("SELECT id, direction_id, kind FROM discipline ORDER BY id").all() == [
        (1, 2, "regular"),
        (2, 1, "practice"),
        (3, 2, "regular"),
        (4, 2, "regular"),
    ]
    # Компетенция – там, где ее формируют дисциплины, несвязанная – в основном направлении.
    assert sql("SELECT id, direction_id FROM competency ORDER BY id").all() == [
        (1, 2),
        (2, 1),
        (3, 2),
    ]
    # Связи, индикаторы и вопросы на месте.
    assert sql("SELECT COUNT(*) FROM discipline_competency").scalar() == 2
    assert sql("SELECT COUNT(*) FROM labor_function_competency").scalar() == 1
    assert sql("SELECT code FROM indicator").scalar() == "ПК-1.1"
    assert sql("SELECT competency_id FROM question").scalar() == 1
    # Тот же код компетенции и то же название дисциплины – в другом направлении можно.
    sql(
        "INSERT INTO competency (direction_id, code, kind, description) "
        "VALUES (1, 'ПК-1', 'ПК', 'x')"
    )
    sql("INSERT INTO discipline (direction_id, name) VALUES (1, 'Базы данных')")
    connection.close()


def test_catalogs_without_direction_get_a_placeholder(tmp_path):
    connection = _upgrade_with(
        tmp_path,
        ["INSERT INTO competency (id, code, kind, description) VALUES (1, 'УК-1', 'УК', 'у')"],
    )
    sql = connection.exec_driver_sql
    assert sql(
        "SELECT d.code FROM competency c JOIN direction d ON d.id = c.direction_id"
    ).one() == ("00.00.00",)
    connection.close()


PLANS_BASE = "fdfafee8b950"


def test_directions_become_plans_without_changes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    config = Config(str(ALEMBIC_INI))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, PLANS_BASE)
        connection.exec_driver_sql(
            "INSERT INTO direction (id, code, name) VALUES (7, '15.04.06', 'М')"
        )
        command.upgrade(config, "head")
        sql = connection.exec_driver_sql
        assert sql(
            "SELECT id, code, name, profile, plan_year, profile_key FROM direction"
        ).one() == (
            7,
            "15.04.06",
            "М",
            None,
            None,
            "",
        )
        sql(
            "INSERT INTO direction (code, name, profile_key, plan_year) VALUES ('15.04.06', 'М', '', 2026)"
        )
        with pytest.raises(IntegrityError):
            sql("INSERT INTO direction (code, name, profile_key) VALUES ('15.04.06', 'Д', '')")


def test_downgrade_refuses_when_code_has_several_plans(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    config = Config(str(ALEMBIC_INI))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        connection.exec_driver_sql(
            "INSERT INTO direction (code, name, profile_key, plan_year) VALUES "
            "('11.03.02', 'С', '', 2023), ('11.03.02', 'С', '', 2026)"
        )
        with pytest.raises(RuntimeError, match="11.03.02"):
            command.downgrade(config, PLANS_BASE)
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM direction").scalar() == 2
