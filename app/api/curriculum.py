"""Учебный план: в каких семестрах направления изучается дисциплина, кто разрабатывает по ней
вопросы и сколько вопросов нужно на каждую компетенцию."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.api.deps import SessionDep, require_admin
from app.errors import DomainError
from app.services.common import get_or_404, save

router = APIRouter(tags=["Учебный план"], dependencies=[Depends(require_admin)])


def _apply(session: SessionDep, entry: models.CurriculumEntry, data: schemas.CurriculumEntryIn):
    get_or_404(session, models.Direction, data.direction_id)
    discipline = get_or_404(session, models.Discipline, data.discipline_id)
    if data.teacher_id is not None:
        teacher = get_or_404(session, models.User, data.teacher_id)
        if teacher.role != models.Role.TEACHER:
            raise DomainError("закрепить дисциплину можно только за преподавателем")
    allowed = set(discipline.competency_ids)
    if any(q.competency_id not in allowed for q in data.quotas):
        raise DomainError(f"квота задана для компетенции, которую «{discipline.name}» не формирует")
    if len({q.competency_id for q in data.quotas}) != len(data.quotas):
        raise DomainError("у одной компетенции может быть только одна квота")
    for field in ("direction_id", "discipline_id", "first_semester", "last_semester", "teacher_id"):
        setattr(entry, field, getattr(data, field))
    entry.quotas = [
        models.CurriculumQuota(competency_id=q.competency_id, questions=q.questions)
        for q in data.quotas
    ]


@router.get("/curriculum", response_model=list[schemas.CurriculumEntryOut])
def list_curriculum(session: SessionDep, direction_id: int | None = None):
    stmt = (
        select(models.CurriculumEntry)
        .join(models.Discipline)
        .order_by(models.CurriculumEntry.last_semester, models.Discipline.name)
        .options(selectinload(models.CurriculumEntry.quotas))
    )
    if direction_id is not None:
        stmt = stmt.where(models.CurriculumEntry.direction_id == direction_id)
    return session.scalars(stmt).all()


@router.post("/curriculum", response_model=schemas.CurriculumEntryOut, status_code=201)
def create_entry(data: schemas.CurriculumEntryIn, session: SessionDep):
    entry = models.CurriculumEntry()
    _apply(session, entry, data)
    return save(session, entry)


@router.put("/curriculum/{entry_id}", response_model=schemas.CurriculumEntryOut)
def update_entry(entry_id: int, data: schemas.CurriculumEntryIn, session: SessionDep):
    entry = get_or_404(session, models.CurriculumEntry, entry_id)
    entry.quotas = []
    session.flush()  # старые квоты удаляются до вставки новых с тем же ключом
    _apply(session, entry, data)
    session.commit()
    return entry


@router.delete("/curriculum/{entry_id}", status_code=204)
def delete_entry(entry_id: int, session: SessionDep):
    entry = get_or_404(session, models.CurriculumEntry, entry_id)
    session.delete(entry)
    session.commit()
