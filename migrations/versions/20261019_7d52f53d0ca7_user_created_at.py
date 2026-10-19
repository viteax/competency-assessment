"""user created at

Revision ID: 7d52f53d0ca7
Revises: 1511906f3586
Create Date: 2026-10-19 20:39:56.237294

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d52f53d0ca7"
down_revision: str | Sequence[str] | None = "1511906f3586"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch — потому что SQLite не умеет добавлять столбец с default now() через ALTER TABLE.
    with op.batch_alter_table("app_user") as batch:
        batch.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("app_user") as batch:
        batch.drop_column("created_at")
