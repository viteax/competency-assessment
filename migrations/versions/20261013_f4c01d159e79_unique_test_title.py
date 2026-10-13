"""unique test title

Revision ID: f4c01d159e79
Revises: 17e6b21ffe97
Create Date: 2026-10-13 19:55:36.331414

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4c01d159e79"
down_revision: str | Sequence[str] | None = "17e6b21ffe97"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # До этой ревизии названия тестов могли повторяться (по умолчанию подставлялось
    # «Входной контроль»). Дубли переименовываем в «… (2)», «… (3)», иначе ограничение
    # не применится. Сравнение — без учёта регистра и лишних пробелов, как в приложении.
    bind = op.get_bind()
    test = sa.table("test", sa.column("id", sa.Integer), sa.column("title", sa.String))
    rows = bind.execute(sa.select(test.c.id, test.c.title).order_by(test.c.id)).all()
    taken = {" ".join(title.split()).casefold() for _, title in rows}
    seen: set[str] = set()
    for test_id, title in rows:
        key = " ".join(title.split()).casefold()
        if key not in seen:
            seen.add(key)
            continue
        n = 2
        while f"{key} ({n})" in taken:
            n += 1
        new_title = f"{title} ({n})"
        taken.add(f"{key} ({n})")
        seen.add(f"{key} ({n})")
        bind.execute(test.update().where(test.c.id == test_id).values(title=new_title))

    with op.batch_alter_table("test") as batch:
        batch.create_unique_constraint("uq_test_title", ["title"])


def downgrade() -> None:
    with op.batch_alter_table("test") as batch:
        batch.drop_constraint("uq_test_title", type_="unique")
