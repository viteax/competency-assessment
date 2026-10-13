"""Компетенции, индикаторы, дисциплины."""

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.api.deps import SessionDep
from app.services.common import get_many_or_404, get_or_404

router = APIRouter(tags=["Компетенции"])


@router.post("/competencies", response_model=schemas.CompetencyOut, status_code=201)
def create_competency(data: schemas.CompetencyIn, session: SessionDep):
    competency = models.Competency(
        code=data.code,
        kind=data.kind,
        description=data.description,
        indicators=[models.Indicator(**i.model_dump()) for i in data.indicators],
    )
    session.add(competency)
    session.commit()
    return competency


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


@router.post(
    "/competencies/{competency_id}/indicators",
    response_model=schemas.IndicatorOut,
    status_code=201,
)
def add_indicator(competency_id: int, data: schemas.IndicatorIn, session: SessionDep):
    competency = get_or_404(session, models.Competency, competency_id)
    indicator = models.Indicator(**data.model_dump())
    competency.indicators.append(indicator)
    session.commit()
    return indicator


@router.post("/disciplines", response_model=schemas.DisciplineOut, status_code=201)
def create_discipline(data: schemas.DisciplineIn, session: SessionDep):
    discipline = models.Discipline(
        name=data.name,
        competencies=get_many_or_404(session, models.Competency, data.competency_ids),
    )
    session.add(discipline)
    session.commit()
    return discipline


@router.get("/disciplines", response_model=list[schemas.DisciplineOut])
def list_disciplines(session: SessionDep):
    return session.scalars(
        select(models.Discipline)
        .order_by(models.Discipline.name)
        .options(selectinload(models.Discipline.competencies))
    ).all()


@router.put("/disciplines/{discipline_id}/competencies", response_model=schemas.DisciplineOut)
def set_discipline_competencies(discipline_id: int, competency_ids: list[int], session: SessionDep):
    discipline = get_or_404(session, models.Discipline, discipline_id)
    discipline.competencies = get_many_or_404(session, models.Competency, competency_ids)
    session.commit()
    return discipline
