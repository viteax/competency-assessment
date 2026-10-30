"""direction plans

Направление становится учебным планом: у одного кода может быть несколько планов с разными
программами и годами. Существующие записи не меняются, программа и год у них пустые.

Откат невозможен, если у какого-то кода уже несколько планов: остановится с ошибкой, данные
не удаляются.

Revision ID: a3c1d7e92b40
Revises: fdfafee8b950
Create Date: 2026-10-30 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c1d7e92b40"
down_revision: str | Sequence[str] | None = "fdfafee8b950"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SQLITE_NAMES = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def _code_unique() -> str:
    """Имя безымянного ограничения первой миграции зависит от базы."""
    return (
        "direction_code_key" if op.get_bind().dialect.name == "postgresql" else "uq_direction_code"
    )


def upgrade() -> None:
    with op.batch_alter_table("direction", naming_convention=SQLITE_NAMES) as batch:
        batch.add_column(sa.Column("profile", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("plan_year", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("profile_key", sa.String(length=255), server_default="", nullable=False)
        )
        batch.drop_constraint(_code_unique(), type_="unique")
    op.create_index(
        "uq_direction_plan",
        "direction",
        ["code", "profile_key", sa.text("coalesce(plan_year, 0)")],
        unique=True,
    )


def downgrade() -> None:
    several = (
        op.get_bind()
        .execute(sa.text("SELECT code FROM direction GROUP BY code HAVING COUNT(*) > 1"))
        .scalars()
        .all()
    )
    if several:
        raise RuntimeError(f"у кодов несколько учебных планов: {', '.join(several)}")
    op.drop_index("uq_direction_plan", table_name="direction")
    with op.batch_alter_table("direction", naming_convention=SQLITE_NAMES) as batch:
        batch.create_unique_constraint(_code_unique(), ["code"])
        batch.drop_column("profile_key")
        batch.drop_column("plan_year")
        batch.drop_column("profile")
