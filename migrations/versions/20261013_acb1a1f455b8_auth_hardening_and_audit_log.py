"""auth hardening and audit log

Revision ID: acb1a1f455b8
Revises: f4c01d159e79
Create Date: 2026-10-13 20:38:38.110273

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "acb1a1f455b8"
down_revision: str | Sequence[str] | None = "f4c01d159e79"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_failure",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_login_failure_created_at"), "login_failure", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_login_failure_ip"), "login_failure", ["ip"], unique=False)
    op.create_index(op.f("ix_login_failure_username"), "login_failure", ["username"], unique=False)
    op.create_table(
        "audit_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_entry_created_at"), "audit_entry", ["created_at"], unique=False)
    with op.batch_alter_table("app_user") as batch:
        batch.add_column(
            sa.Column(
                "must_change_password",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("token_version", sa.Integer(), server_default="0", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("app_user") as batch:
        batch.drop_column("token_version")
        batch.drop_column("must_change_password")
    op.drop_index(op.f("ix_audit_entry_created_at"), table_name="audit_entry")
    op.drop_table("audit_entry")
    op.drop_index(op.f("ix_login_failure_username"), table_name="login_failure")
    op.drop_index(op.f("ix_login_failure_ip"), table_name="login_failure")
    op.drop_index(op.f("ix_login_failure_created_at"), table_name="login_failure")
    op.drop_table("login_failure")
