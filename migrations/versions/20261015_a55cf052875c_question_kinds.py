"""question kinds

Revision ID: a55cf052875c
Revises: 075522b81f9b
Create Date: 2026-10-15 20:36:10.114630

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a55cf052875c"
down_revision: str | Sequence[str] | None = "075522b81f9b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


QUESTION_KIND = sa.Enum("single", "matching", "sequence", "open", name="questionkind")
DIFFICULTY = sa.Enum("basic", "advanced", name="difficulty")


def upgrade() -> None:
    bind = op.get_bind()
    QUESTION_KIND.create(bind, checkfirst=True)
    DIFFICULTY.create(bind, checkfirst=True)
    # Все существующие вопросы – с выбором одного ответа, базового уровня.
    op.add_column(
        "question", sa.Column("kind", QUESTION_KIND, server_default="single", nullable=False)
    )
    op.add_column(
        "question", sa.Column("difficulty", DIFFICULTY, server_default="basic", nullable=False)
    )
    op.add_column("attempt_answer", sa.Column("response", sa.Text(), nullable=True))
    op.add_column(
        "answer_option", sa.Column("position", sa.Integer(), server_default="0", nullable=False)
    )
    with op.batch_alter_table("answer_option") as batch:
        batch.add_column(sa.Column("match_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_answer_option_match", "answer_option", ["match_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("answer_option") as batch:
        batch.drop_constraint("fk_answer_option_match", type_="foreignkey")
        batch.drop_column("match_id")
    op.drop_column("answer_option", "position")
    op.drop_column("attempt_answer", "response")
    op.drop_column("question", "difficulty")
    op.drop_column("question", "kind")
    bind = op.get_bind()
    DIFFICULTY.drop(bind, checkfirst=True)
    QUESTION_KIND.drop(bind, checkfirst=True)
