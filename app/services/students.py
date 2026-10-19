"""Студенты: правила, которые касаются не только записи в справочнике."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import models
from app.errors import Conflict
from app.services.common import delete_or_conflict


def delete_student(session: Session, student: models.Student) -> None:
    """Удаляет студента вместе с его учётной записью. Студента с результатами тестов удалить
    нельзя – пропали бы данные отчётов; его можно перевести в другую группу."""
    if session.scalar(select(models.Attempt.id).where(models.Attempt.student_id == student.id)):
        raise Conflict("у студента есть результаты тестов – удалить нельзя")
    session.execute(delete(models.User).where(models.User.student_id == student.id))
    delete_or_conflict(session, student, "на студента есть ссылки")
