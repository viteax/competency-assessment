"""curriculum and test variants

Revision ID: 075522b81f9b
Revises: 04ba11049bad
Create Date: 2026-10-15 19:20:57.222446

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "075522b81f9b"
down_revision: str | Sequence[str] | None = "04ba11049bad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "curriculum_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("direction_id", sa.Integer(), nullable=False),
        sa.Column("discipline_id", sa.Integer(), nullable=False),
        sa.Column("first_semester", sa.Integer(), nullable=False),
        sa.Column("last_semester", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "first_semester >= 1 AND first_semester <= last_semester AND last_semester <= 12",
            name="ck_curriculum_semesters",
        ),
        sa.ForeignKeyConstraint(["direction_id"], ["direction.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["discipline_id"], ["discipline.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("direction_id", "discipline_id", name="uq_curriculum_entry"),
    )
    op.create_table(
        "test_discipline",
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("discipline_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["discipline_id"], ["discipline.id"]),
        sa.ForeignKeyConstraint(["test_id"], ["test.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("test_id", "discipline_id"),
    )
    op.add_column("attempt", sa.Column("variant", sa.Integer(), server_default="1", nullable=False))
    op.add_column("study_group", sa.Column("start_year", sa.Integer(), nullable=True))
    op.add_column("test", sa.Column("semester", sa.Integer(), nullable=True))
    op.add_column(
        "test_question", sa.Column("variant", sa.Integer(), server_default="1", nullable=False)
    )

    # Дисциплина теста переезжает в связь «тест – дисциплины»: тест можно собрать из нескольких.
    op.execute(
        "INSERT INTO test_discipline (test_id, discipline_id) "
        "SELECT id, discipline_id FROM test WHERE discipline_id IS NOT NULL"
    )
    with op.batch_alter_table("test") as batch:
        batch.drop_column("discipline_id")


def downgrade() -> None:
    with op.batch_alter_table("test") as batch:
        batch.add_column(sa.Column("discipline_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_test_discipline", "discipline", ["discipline_id"], ["id"])
    # Обратно переносится одна дисциплина на тест (с наименьшим id).
    op.execute(
        "UPDATE test SET discipline_id = "
        "(SELECT MIN(discipline_id) FROM test_discipline WHERE test_discipline.test_id = test.id)"
    )
    op.drop_column("test_question", "variant")
    op.drop_column("test", "semester")
    op.drop_column("study_group", "start_year")
    op.drop_column("attempt", "variant")
    op.drop_table("test_discipline")
    op.drop_table("curriculum_entry")
