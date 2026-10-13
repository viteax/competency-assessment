"""student email and external id

Revision ID: 17e6b21ffe97
Revises: 7db2ffb41d46
Create Date: 2026-10-13 17:44:04.842022

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "17e6b21ffe97"
down_revision: str | Sequence[str] | None = "7db2ffb41d46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("student") as batch:
        batch.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("external_id", sa.String(length=64), nullable=True))
        batch.create_unique_constraint("uq_student_external_id", ["external_id"])


def downgrade() -> None:
    with op.batch_alter_table("student") as batch:
        batch.drop_constraint("uq_student_external_id", type_="unique")
        batch.drop_column("external_id")
        batch.drop_column("email")
