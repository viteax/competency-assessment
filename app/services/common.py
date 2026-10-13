from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base
from app.errors import Conflict, NotFound


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
