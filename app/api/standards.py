"""Профстандарты: ОТФ, ТФ и их связь с компетенциями."""

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.api.deps import SessionDep
from app.services.common import get_many_or_404, get_or_404

router = APIRouter(tags=["Профстандарты"])


@router.post("/standards", response_model=schemas.ProfStandardOut, status_code=201)
def create_standard(data: schemas.ProfStandardIn, session: SessionDep):
    standard = models.ProfStandard(
        code=data.code,
        name=data.name,
        general_functions=[
            models.GeneralLaborFunction(
                code=g.code,
                name=g.name,
                qualification_level=g.qualification_level,
                functions=[
                    models.LaborFunction(
                        code=f.code,
                        name=f.name,
                        competencies=get_many_or_404(session, models.Competency, f.competency_ids),
                    )
                    for f in g.functions
                ],
            )
            for g in data.general_functions
        ],
    )
    session.add(standard)
    session.commit()
    return standard


@router.get("/standards", response_model=list[schemas.ProfStandardOut])
def list_standards(session: SessionDep):
    return session.scalars(
        select(models.ProfStandard)
        .order_by(models.ProfStandard.code)
        .options(
            selectinload(models.ProfStandard.general_functions)
            .selectinload(models.GeneralLaborFunction.functions)
            .selectinload(models.LaborFunction.competencies)
        )
    ).all()


@router.put(
    "/labor-functions/{labor_function_id}/competencies",
    response_model=schemas.LaborFunctionOut,
)
def set_labor_function_competencies(
    labor_function_id: int, competency_ids: list[int], session: SessionDep
):
    """Связь ТФ ⇒ ПК: какие компетенции нужны для выполнения трудовой функции."""
    labor_function = get_or_404(session, models.LaborFunction, labor_function_id)
    labor_function.competencies = get_many_or_404(session, models.Competency, competency_ids)
    session.commit()
    return labor_function
