"""attempt draft

Черновик ответов студента по ходу теста: сохраняется автоматически, стирается при сдаче.

Revision ID: f80e0e615d56
Revises: 3c9e1f7a2b64
Create Date: 2026-10-21 17:52:21.837510

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f80e0e615d56"
down_revision: str | Sequence[str] | None = "3c9e1f7a2b64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("attempt", schema=None) as batch_op:
        batch_op.add_column(sa.Column("draft", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("attempt", schema=None) as batch_op:
        batch_op.drop_column("draft")
