"""teachers and quotas

Revision ID: e0573d4a3b5e
Revises: a55cf052875c
Create Date: 2026-10-19 20:01:29.714621

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e0573d4a3b5e"
down_revision: str | Sequence[str] | None = "a55cf052875c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Новое значение перечисления ролей (в SQLite роль — просто строка).
        op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'teacher' BEFORE 'student'")
    op.add_column("app_user", sa.Column("full_name", sa.String(length=255), nullable=True))
    with op.batch_alter_table("curriculum_entry") as batch:
        batch.add_column(sa.Column("teacher_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_curriculum_entry_teacher", "app_user", ["teacher_id"], ["id"], ondelete="SET NULL"
        )
    op.create_table(
        "curriculum_quota",
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("competency_id", sa.Integer(), nullable=False),
        sa.Column("questions", sa.Integer(), nullable=False),
        sa.CheckConstraint("questions >= 1", name="ck_curriculum_quota_positive"),
        sa.ForeignKeyConstraint(["competency_id"], ["competency.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entry_id"], ["curriculum_entry.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("entry_id", "competency_id"),
    )


def downgrade() -> None:
    op.drop_table("curriculum_quota")
    with op.batch_alter_table("curriculum_entry") as batch:
        batch.drop_constraint("fk_curriculum_entry_teacher", type_="foreignkey")
        batch.drop_column("teacher_id")
    op.drop_column("app_user", "full_name")
    # Значение 'teacher' из перечисления PostgreSQL не удаляется (это не поддерживается);
    # учётки преподавателей при откате нужно удалить заранее.
    op.execute("DELETE FROM app_user WHERE role = 'teacher'")
