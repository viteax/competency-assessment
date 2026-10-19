"""overlapping variants

Revision ID: 1511906f3586
Revises: e0573d4a3b5e
Create Date: 2026-10-19 20:16:46.520934

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1511906f3586"
down_revision: str | Sequence[str] | None = "e0573d4a3b5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rebuild(primary_key: tuple[str, ...]) -> None:
    """Пересоздаёт test_question с другим первичным ключом, сохраняя данные (так одинаково
    работает и в PostgreSQL, и в SQLite)."""
    op.create_table(
        "test_question_new",
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("variant", sa.Integer(), server_default="1", nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"]),
        sa.ForeignKeyConstraint(["test_id"], ["test.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint(*primary_key, name="test_question_new_pkey"),
    )
    op.execute(
        "INSERT INTO test_question_new (test_id, variant, question_id, position) "
        "SELECT test_id, variant, question_id, position FROM test_question"
    )
    op.drop_table("test_question")
    op.rename_table("test_question_new", "test_question")
    if op.get_bind().dialect.name == "postgresql":
        # Имена ограничений в PostgreSQL общие на схему — возвращаем привычное имя ключа.
        op.execute(
            "ALTER TABLE test_question RENAME CONSTRAINT test_question_new_pkey "
            "TO test_question_pkey"
        )


def upgrade() -> None:
    # Один вопрос теперь может входить в несколько вариантов теста: вариант — часть ключа.
    _rebuild(("test_id", "variant", "question_id"))


def downgrade() -> None:
    # Повторы вопроса в разных вариантах в старой схеме невозможны — оставляем первый.
    op.execute(
        "DELETE FROM test_question WHERE EXISTS (SELECT 1 FROM test_question t2 "
        "WHERE t2.test_id = test_question.test_id "
        "AND t2.question_id = test_question.question_id AND t2.variant < test_question.variant)"
    )
    _rebuild(("test_id", "question_id"))
