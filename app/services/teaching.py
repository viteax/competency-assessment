"""Преподаватели: закреплённые дисциплины, квоты вопросов и права на банк вопросов."""

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.errors import DomainError, Forbidden, NotFound
from app.services.common import code_key


def entries_of(session: Session, teacher: models.User) -> list[models.CurriculumEntry]:
    return list(
        session.scalars(
            select(models.CurriculumEntry)
            .where(models.CurriculumEntry.teacher_id == teacher.id)
            .options(
                selectinload(models.CurriculumEntry.discipline).selectinload(
                    models.Discipline.competencies
                ),
                selectinload(models.CurriculumEntry.direction),
                selectinload(models.CurriculumEntry.quotas),
            )
        )
    )


def discipline_ids_of(session: Session, teacher: models.User) -> set[int]:
    return set(
        session.scalars(
            select(models.CurriculumEntry.discipline_id).where(
                models.CurriculumEntry.teacher_id == teacher.id
            )
        )
    )


def check_question_access(
    session: Session, user: models.User, discipline_id: int | None, competency_id: int
) -> None:
    """Преподаватель работает только с вопросами своих дисциплин и только по компетенциям,
    которые эта дисциплина формирует. Администратору можно всё."""
    if user.role == models.Role.ADMIN:
        return
    if discipline_id is None or discipline_id not in discipline_ids_of(session, user):
        raise Forbidden("эта дисциплина не закреплена за вами")
    discipline = session.get(models.Discipline, discipline_id)
    if competency_id not in discipline.competency_ids:
        raise DomainError(f"дисциплина «{discipline.name}» не формирует эту компетенцию")


def progress(session: Session, teacher: models.User) -> list[schemas.TeacherDiscipline]:
    return entries_progress(session, entries_of(session, teacher))


def entries_progress(
    session: Session, entries: list[models.CurriculumEntry]
) -> list[schemas.TeacherDiscipline]:
    """Квоты и сколько вопросов уже есть по каждой компетенции строк учебного плана."""
    counts = Counter(
        {
            (discipline_id, competency_id): n
            for discipline_id, competency_id, n in session.execute(
                select(models.Question.discipline_id, models.Question.competency_id, func.count())
                .where(models.Question.discipline_id.in_([e.discipline_id for e in entries]))
                .group_by(models.Question.discipline_id, models.Question.competency_id)
            )
        }
    )
    result = []
    for e in sorted(entries, key=lambda e: (e.discipline.name, e.direction.code)):
        quotas = {q.competency_id: q.questions for q in e.quotas}
        rows = [
            schemas.QuotaProgress(
                competency_id=c.id,
                code=c.code,
                description=c.description,
                required=quotas.get(c.id, 0),
                done=counts[(e.discipline_id, c.id)],
            )
            for c in sorted(e.discipline.competencies, key=lambda c: code_key(c.code))
        ]
        result.append(
            schemas.TeacherDiscipline(
                entry_id=e.id,
                discipline_id=e.discipline_id,
                discipline=e.discipline.name,
                direction=f"{e.direction.code} {e.direction.name}",
                first_semester=e.first_semester,
                last_semester=e.last_semester,
                competencies=rows,
                required=sum(r.required for r in rows),
                done=sum(min(r.done, r.required) for r in rows),
            )
        )
    return result


def own_discipline(session: Session, teacher: models.User, discipline_id: int) -> None:
    if discipline_id not in discipline_ids_of(session, teacher):
        raise NotFound(f"дисциплина {discipline_id} за вами не закреплена")
