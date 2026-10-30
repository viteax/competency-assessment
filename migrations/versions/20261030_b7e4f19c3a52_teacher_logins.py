"""teacher logins

Логины преподавателей из одних цифр (111, 222) заменяются на фамилию и инициалы: «Иванов И.И.»,
при совпадении – «Иванов И.И.2». Пароли не меняются, журнал действий хранит прежние логины.

Откат ничего не делает: старые логины нигде не сохраняются.

Revision ID: b7e4f19c3a52
Revises: a3c1d7e92b40
Create Date: 2026-10-30 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e4f19c3a52"
down_revision: str | Sequence[str] | None = "a3c1d7e92b40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _login(full_name: str) -> str:
    surname, *rest = full_name.split()
    initials = "".join(f"{p[0].upper()}." for p in rest[:2])
    return f"{surname} {initials}".strip()


def upgrade() -> None:
    bind = op.get_bind()
    users = bind.execute(sa.text("SELECT id, username, role, full_name FROM app_user ORDER BY id"))
    rows = users.all()
    taken = {row.username for row in rows}
    for row in rows:
        full_name = (row.full_name or "").strip()
        if row.role != "teacher" or not row.username.isdigit() or not full_name:
            continue
        base = _login(full_name)
        candidate, n = base, 1
        while candidate in taken:
            n += 1
            candidate = f"{base}{n}"
        taken.add(candidate)
        bind.execute(
            sa.text("UPDATE app_user SET username = :username WHERE id = :id"),
            {"username": candidate, "id": row.id},
        )


def downgrade() -> None:
    pass
