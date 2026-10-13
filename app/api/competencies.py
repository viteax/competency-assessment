"""Компетенции, индикаторы, дисциплины."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.api.deps import SessionDep, require_admin
from app.services.common import delete_or_conflict, get_many_or_404, get_or_404, save, update_fields

router = APIRouter(tags=["Компетенции"], dependencies=[Depends(require_admin)])


@router.post("/competencies", response_model=schemas.CompetencyOut, status_code=201)
def create_competency(data: schemas.CompetencyIn, session: SessionDep):
    return save(
        session,
        models.Competency(
            code=data.code,
            kind=data.kind,
            description=data.description,
            indicators=[models.Indicator(**i.model_dump()) for i in data.indicators],
        ),
    )


@router.get("/competencies", response_model=list[schemas.CompetencyOut])
def list_competencies(session: SessionDep, kind: models.CompetencyKind | None = None):
    stmt = (
        select(models.Competency)
        .order_by(models.Competency.code)
        .options(selectinload(models.Competency.indicators))
    )
    if kind is not None:
        stmt = stmt.where(models.Competency.kind == kind)
    return session.scalars(stmt).all()


@router.put("/competencies/{competency_id}", response_model=schemas.CompetencyOut)
def update_competency(competency_id: int, data: schemas.CompetencyUpdate, session: SessionDep):
    competency = get_or_404(session, models.Competency, competency_id)
    return update_fields(session, competency, data)


@router.delete("/competencies/{competency_id}", status_code=204)
def delete_competency(competency_id: int, session: SessionDep):
    competency = get_or_404(session, models.Competency, competency_id)
    delete_or_conflict(session, competency, "по компетенции есть вопросы в банке")


# --- Индикаторы ------------------------------------------------------------


@router.get("/indicators", response_model=list[schemas.IndicatorOut])
def list_indicators(session: SessionDep, competency_id: int | None = None):
    stmt = select(models.Indicator).order_by(models.Indicator.code)
    if competency_id is not None:
        stmt = stmt.where(models.Indicator.competency_id == competency_id)
    return session.scalars(stmt).all()


@router.post("/indicators", response_model=schemas.IndicatorOut, status_code=201)
def create_indicator(data: schemas.IndicatorCreate, session: SessionDep):
    get_or_404(session, models.Competency, data.competency_id)
    return save(session, models.Indicator(**data.model_dump()))


@router.put("/indicators/{indicator_id}", response_model=schemas.IndicatorOut)
def update_indicator(indicator_id: int, data: schemas.IndicatorIn, session: SessionDep):
    indicator = get_or_404(session, models.Indicator, indicator_id)
    return update_fields(session, indicator, data)


@router.delete("/indicators/{indicator_id}", status_code=204)
def delete_indicator(indicator_id: int, session: SessionDep):
    indicator = get_or_404(session, models.Indicator, indicator_id)
    delete_or_conflict(session, indicator, "к индикатору привязаны вопросы")


# --- Дисциплины ------------------------------------------------------------


@router.post("/disciplines", response_model=schemas.DisciplineOut, status_code=201)
def create_discipline(data: schemas.DisciplineIn, session: SessionDep):
    return save(
        session,
        models.Discipline(
            name=data.name,
            competencies=get_many_or_404(session, models.Competency, data.competency_ids),
        ),
    )


@router.get("/disciplines", response_model=list[schemas.DisciplineOut])
def list_disciplines(session: SessionDep):
    return session.scalars(
        select(models.Discipline)
        .order_by(models.Discipline.name)
        .options(selectinload(models.Discipline.competencies))
    ).all()


@router.put("/disciplines/{discipline_id}", response_model=schemas.DisciplineOut)
def update_discipline(discipline_id: int, data: schemas.DisciplineIn, session: SessionDep):
    discipline = get_or_404(session, models.Discipline, discipline_id)
    return update_fields(
        session,
        discipline,
        name=data.name,
        competencies=get_many_or_404(session, models.Competency, data.competency_ids),
    )


@router.delete("/disciplines/{discipline_id}", status_code=204)
def delete_discipline(discipline_id: int, session: SessionDep):
    discipline = get_or_404(session, models.Discipline, discipline_id)
    delete_or_conflict(session, discipline, "к дисциплине привязаны вопросы или тесты")
