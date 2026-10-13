"""initial schema

Revision ID: 7db2ffb41d46
Revises:
Create Date: 2026-10-13 16:32:35.631928

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7db2ffb41d46"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "competency",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.Enum("УК", "ОПК", "ПК", name="competencykind"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "direction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "discipline",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "prof_standard",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "discipline_competency",
        sa.Column("discipline_id", sa.Integer(), nullable=False),
        sa.Column("competency_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["competency_id"], ["competency.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["discipline_id"], ["discipline.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("discipline_id", "competency_id"),
    )
    op.create_table(
        "general_labor_function",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("standard_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("qualification_level", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["standard_id"], ["prof_standard.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("standard_id", "code"),
    )
    op.create_table(
        "indicator",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competency_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["competency_id"], ["competency.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "study_group",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("direction_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["direction_id"],
            ["direction.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "test",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("discipline_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["discipline_id"],
            ["discipline.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "assignment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["study_group.id"],
        ),
        sa.ForeignKeyConstraint(
            ["test_id"],
            ["test.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("test_id", "group_id"),
    )
    op.create_table(
        "labor_function",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("general_function_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["general_function_id"], ["general_labor_function.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("general_function_id", "code"),
    )
    op.create_table(
        "question",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competency_id", sa.Integer(), nullable=False),
        sa.Column("indicator_id", sa.Integer(), nullable=True),
        sa.Column("discipline_id", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["competency_id"],
            ["competency.id"],
        ),
        sa.ForeignKeyConstraint(
            ["discipline_id"],
            ["discipline.id"],
        ),
        sa.ForeignKeyConstraint(
            ["indicator_id"],
            ["indicator.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "student",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["study_group.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "answer_option",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "app_user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum("admin", "student", name="role"), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["student.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "attempt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("max_score", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignment.id"],
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["student.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "student_id"),
    )
    op.create_table(
        "labor_function_competency",
        sa.Column("labor_function_id", sa.Integer(), nullable=False),
        sa.Column("competency_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["competency_id"], ["competency.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["labor_function_id"], ["labor_function.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("labor_function_id", "competency_id"),
    )
    op.create_table(
        "test_question",
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["question.id"],
        ),
        sa.ForeignKeyConstraint(["test_id"], ["test.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("test_id", "question_id"),
    )
    op.create_table(
        "attempt_answer",
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("option_id", sa.Integer(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempt.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["option_id"],
            ["answer_option.id"],
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["question.id"],
        ),
        sa.PrimaryKeyConstraint("attempt_id", "question_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("attempt_answer")
    op.drop_table("test_question")
    op.drop_table("labor_function_competency")
    op.drop_table("attempt")
    op.drop_table("app_user")
    op.drop_table("answer_option")
    op.drop_table("student")
    op.drop_table("question")
    op.drop_table("labor_function")
    op.drop_table("assignment")
    op.drop_table("test")
    op.drop_table("study_group")
    op.drop_table("indicator")
    op.drop_table("general_labor_function")
    op.drop_table("discipline_competency")
    op.drop_table("prof_standard")
    op.drop_table("discipline")
    op.drop_table("direction")
    op.drop_table("competency")
    # В PostgreSQL enum-типы живут отдельно от таблиц.
    bind = op.get_bind()
    sa.Enum(name="role").drop(bind, checkfirst=True)
    sa.Enum(name="competencykind").drop(bind, checkfirst=True)
