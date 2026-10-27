"""direction scoped catalogs

Компетенции и дисциплины принадлежат направлению: в разных ОП коды компетенций совпадают, а
формулировки бывают разные. У дисциплины появляются индекс в учебном плане и статус
(обязательная, по выбору, факультатив, практика).

Существующие записи получают направление по учебному плану: дисциплина – направление своей
строки плана, компетенция – направление, в котором ее формирует больше всего дисциплин.
Остальные – основное направление (с наибольшим числом строк плана). Если компетенции есть, а
направлений нет, создается направление «00.00.00 Направление не указано» – его нужно
переименовать.

Откат вернет общие справочники, если в разных направлениях нет одинаковых кодов компетенций
и названий дисциплин.

Revision ID: fdfafee8b950
Revises: f80e0e615d56
Create Date: 2026-10-27 18:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fdfafee8b950"
down_revision: str | Sequence[str] | None = "f80e0e615d56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DISCIPLINE_KIND = sa.Enum("regular", "elective", "optional", "practice", name="disciplinekind")

# Безымянные ограничения уникальности первой миграции: в PostgreSQL у них имя по умолчанию
# (competency_code_key), в SQLite имя дает naming_convention при пересборке таблицы.
SQLITE_NAMES = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def _initial_unique(table: str, column: str) -> str:
    if op.get_bind().dialect.name == "postgresql":
        return f"{table}_{column}_key"
    return f"uq_{table}_{column}"


def _assign_directions() -> None:
    bind = op.get_bind()

    def sql(query: str, **params):
        return bind.execute(sa.text(query), params)

    if not sql(
        "SELECT (SELECT COUNT(*) FROM competency) + (SELECT COUNT(*) FROM discipline)"
    ).scalar():
        return
    main = (
        sql(
            "SELECT direction_id FROM curriculum_entry GROUP BY direction_id "
            "ORDER BY COUNT(*) DESC, direction_id LIMIT 1"
        ).scalar()
        or sql("SELECT MIN(id) FROM direction").scalar()
    )
    if main is None:
        sql("INSERT INTO direction (code, name) VALUES ('00.00.00', 'Направление не указано')")
        main = sql("SELECT MIN(id) FROM direction").scalar()

    sql(
        "UPDATE discipline SET direction_id = ("
        " SELECT ce.direction_id FROM curriculum_entry ce"
        " WHERE ce.discipline_id = discipline.id ORDER BY ce.id LIMIT 1)"
    )
    sql("UPDATE discipline SET direction_id = :main WHERE direction_id IS NULL", main=main)
    sql(
        "UPDATE competency SET direction_id = ("
        " SELECT d.direction_id FROM discipline_competency dc"
        " JOIN discipline d ON d.id = dc.discipline_id"
        " WHERE dc.competency_id = competency.id"
        " GROUP BY d.direction_id ORDER BY COUNT(*) DESC, d.direction_id LIMIT 1)"
    )
    sql("UPDATE competency SET direction_id = :main WHERE direction_id IS NULL", main=main)
    # Практики узнаются по названию; остальной статус администратор укажет сам или загрузкой УП.
    sql(
        "UPDATE discipline SET kind = 'practice' "
        "WHERE name LIKE '%практика%' OR name LIKE 'Практика%'"
    )


def upgrade() -> None:
    DISCIPLINE_KIND.create(op.get_bind(), checkfirst=True)
    op.add_column("competency", sa.Column("direction_id", sa.Integer(), nullable=True))
    op.add_column("discipline", sa.Column("direction_id", sa.Integer(), nullable=True))
    op.add_column("discipline", sa.Column("code", sa.String(length=32), nullable=True))
    op.add_column(
        "discipline",
        sa.Column("kind", DISCIPLINE_KIND, server_default="regular", nullable=False),
    )

    _assign_directions()

    with op.batch_alter_table("competency", naming_convention=SQLITE_NAMES) as batch:
        batch.alter_column("direction_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_competency_direction", "direction", ["direction_id"], ["id"], ondelete="CASCADE"
        )
        batch.drop_constraint(_initial_unique("competency", "code"), type_="unique")
        batch.create_unique_constraint("uq_competency_direction_code", ["direction_id", "code"])
    with op.batch_alter_table("indicator", naming_convention=SQLITE_NAMES) as batch:
        batch.drop_constraint(_initial_unique("indicator", "code"), type_="unique")
        batch.create_unique_constraint("uq_indicator_competency_code", ["competency_id", "code"])
    with op.batch_alter_table("discipline", naming_convention=SQLITE_NAMES) as batch:
        batch.alter_column("direction_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_discipline_direction", "direction", ["direction_id"], ["id"], ondelete="CASCADE"
        )
        batch.drop_constraint(_initial_unique("discipline", "name"), type_="unique")
        batch.create_unique_constraint("uq_discipline_direction_name", ["direction_id", "name"])


def downgrade() -> None:
    with op.batch_alter_table("discipline", naming_convention=SQLITE_NAMES) as batch:
        batch.drop_constraint("uq_discipline_direction_name", type_="unique")
        batch.create_unique_constraint(_initial_unique("discipline", "name"), ["name"])
        batch.drop_constraint("fk_discipline_direction", type_="foreignkey")
        batch.drop_column("kind")
        batch.drop_column("code")
        batch.drop_column("direction_id")
    with op.batch_alter_table("indicator", naming_convention=SQLITE_NAMES) as batch:
        batch.drop_constraint("uq_indicator_competency_code", type_="unique")
        batch.create_unique_constraint(_initial_unique("indicator", "code"), ["code"])
    with op.batch_alter_table("competency", naming_convention=SQLITE_NAMES) as batch:
        batch.drop_constraint("uq_competency_direction_code", type_="unique")
        batch.create_unique_constraint(_initial_unique("competency", "code"), ["code"])
        batch.drop_constraint("fk_competency_direction", type_="foreignkey")
        batch.drop_column("direction_id")
    DISCIPLINE_KIND.drop(op.get_bind(), checkfirst=True)
