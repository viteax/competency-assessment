"""drop single choice

Кафедра использует три типа заданий: на соответствие, на последовательность и открытого
типа. Вопросы «выбор одного ответа» становятся заданиями открытого типа: правильный вариант
– принимаемый ответ, неверные удаляются. Ответы студентов сохраняются текстом выбранного
варианта, их оценки не пересчитываются.

Revision ID: 3c9e1f7a2b64
Revises: 7d52f53d0ca7
Create Date: 2026-10-20 10:00:00.000000

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c9e1f7a2b64"
down_revision: str | Sequence[str] | None = "7d52f53d0ca7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ("single", "matching", "sequence", "open")
NEW = ("matching", "sequence", "open")


def _set_kinds(values: tuple[str, ...]) -> None:
    """PostgreSQL не умеет удалять значения enum: пересоздаём тип."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TYPE questionkind RENAME TO questionkind_old")
    sa.Enum(*values, name="questionkind").create(op.get_bind())
    op.execute(
        "ALTER TABLE question ALTER COLUMN kind TYPE questionkind USING kind::text::questionkind"
    )
    op.execute("DROP TYPE questionkind_old")


def upgrade() -> None:
    bind = op.get_bind()
    chosen = bind.execute(
        sa.text(
            "SELECT a.attempt_id, a.question_id, o.text FROM attempt_answer a "
            "JOIN answer_option o ON o.id = a.option_id"
        )
    ).all()
    for attempt_id, question_id, text in chosen:
        bind.execute(
            sa.text(
                "UPDATE attempt_answer SET response = :response "
                "WHERE attempt_id = :attempt AND question_id = :question"
            ),
            {
                "response": json.dumps({"text": text}),
                "attempt": attempt_id,
                "question": question_id,
            },
        )
    with op.batch_alter_table("attempt_answer") as batch:
        batch.drop_column("option_id")

    single = "SELECT id FROM question WHERE kind = 'single'"
    bind.execute(
        sa.text(f"DELETE FROM answer_option WHERE NOT is_correct AND question_id IN ({single})")
    )
    bind.execute(sa.text("UPDATE question SET kind = 'open' WHERE kind = 'single'"))
    with op.batch_alter_table("question") as batch:
        batch.alter_column("kind", server_default=None)
    _set_kinds(NEW)


def downgrade() -> None:
    # Удалённые неверные варианты не восстанавливаются: вопросы остаются открытого типа.
    _set_kinds(OLD)
    with op.batch_alter_table("question") as batch:
        batch.alter_column("kind", server_default="single")
    with op.batch_alter_table("attempt_answer") as batch:
        batch.add_column(sa.Column("option_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "attempt_answer_option_id_fkey", "answer_option", ["option_id"], ["id"]
        )
