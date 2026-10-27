import re
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base
from app.errors import Conflict, NotFound

_CODE_GROUPS = ("УК", "ОПК", "ПК")


def code_key(code: str) -> tuple:
    """Порядок кодов как в ФГОС: УК, ОПК, ПК, номера по числу (ОПК-2 раньше ОПК-10).

    Подходит и для индикаторов (УК-1.2 раньше УК-1.10) и для любых других кодов.
    """
    letters = re.match(r"[^\W\d_]*", code).group().upper()
    group = _CODE_GROUPS.index(letters) if letters in _CODE_GROUPS else len(_CODE_GROUPS)
    return (group, *(int(p) if p.isdigit() else p for p in re.split(r"(\d+)", code)))


def name_key(full_name: str) -> tuple[str, ...]:
    """Ключ для сравнения ФИО без учёта порядка слов, регистра и ё/е.

    Moodle часто выводит «Имя Отчество Фамилия», а в деканатских списках «Фамилия Имя
    Отчество» – это один и тот же человек.
    """
    return tuple(sorted(full_name.lower().replace("ё", "е").split()))


def get_or_404[M: Base](session: Session, model: type[M], obj_id: int) -> M:
    obj = session.get(model, obj_id)
    if obj is None:
        raise NotFound(f"{model.__name__} {obj_id} не найден")
    return obj


def get_many_or_404[M: Base](session: Session, model: type[M], ids: list[int]) -> list[M]:
    unique_ids = list(dict.fromkeys(ids))
    objs = session.scalars(select(model).where(model.id.in_(unique_ids))).all()
    found = {o.id for o in objs}
    missing = [i for i in unique_ids if i not in found]
    if missing:
        raise NotFound(f"{model.__name__}: не найдены id {missing}")
    by_id = {o.id: o for o in objs}
    return [by_id[i] for i in unique_ids]


def delete_or_conflict(session: Session, obj: Base, reason: str) -> None:
    """Удаляет запись; если на неё ещё ссылаются, возвращает 409 с понятной причиной."""
    session.delete(obj)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise Conflict(f"нельзя удалить: {reason}") from None


def save[M: Base](session: Session, obj: M) -> M:
    session.add(obj)
    session.commit()
    return obj


def update_fields[M: Base](
    session: Session, obj: M, data: BaseModel | None = None, **values: Any
) -> M:
    """Переносит поля схемы (и/или явно переданные значения) в объект и сохраняет."""
    for name, value in {**(data.model_dump() if data else {}), **values}.items():
        setattr(obj, name, value)
    session.commit()
    return obj
