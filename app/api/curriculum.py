"""Учебный план: в каких семестрах направления изучается дисциплина, кто разрабатывает по ней
вопросы и сколько вопросов нужно на каждую компетенцию."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.api.deps import SessionDep, require_admin
from app.services.common import get_or_404
from app.services.curriculum import save_entry

router = APIRouter(tags=["Учебный план"], dependencies=[Depends(require_admin)])


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
    return save_entry(session, models.CurriculumEntry(), data)


@router.put("/curriculum/{entry_id}", response_model=schemas.CurriculumEntryOut)
def update_entry(entry_id: int, data: schemas.CurriculumEntryIn, session: SessionDep):
    return save_entry(session, get_or_404(session, models.CurriculumEntry, entry_id), data)


@router.delete("/curriculum/{entry_id}", status_code=204)
def delete_entry(entry_id: int, session: SessionDep):
    entry = get_or_404(session, models.CurriculumEntry, entry_id)
    session.delete(entry)
    session.commit()
