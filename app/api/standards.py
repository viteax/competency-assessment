"""Профстандарты: ОТФ, ТФ и их связь с компетенциями."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.api.deps import SessionDep, require_admin
from app.services.common import delete_or_conflict, get_many_or_404, get_or_404, save, update_fields

router = APIRouter(tags=["Профстандарты"], dependencies=[Depends(require_admin)])


@router.post("/standards", response_model=schemas.ProfStandardOut, status_code=201)
def create_standard(data: schemas.ProfStandardIn, session: SessionDep):
    """Создаёт профстандарт сразу с ОТФ и ТФ (удобно для импорта)."""
    return save(
        session,
        models.ProfStandard(
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
                            competencies=get_many_or_404(
                                session, models.Competency, f.competency_ids
                            ),
                        )
                        for f in g.functions
                    ],
                )
                for g in data.general_functions
            ],
        ),
    )


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


@router.put("/standards/{standard_id}", response_model=schemas.ProfStandardOut)
def update_standard(standard_id: int, data: schemas.ProfStandardUpdate, session: SessionDep):
    standard = get_or_404(session, models.ProfStandard, standard_id)
    return update_fields(session, standard, data)


@router.delete("/standards/{standard_id}", status_code=204)
def delete_standard(standard_id: int, session: SessionDep):
    """Удаляет профстандарт вместе с его ОТФ и ТФ."""
    standard = get_or_404(session, models.ProfStandard, standard_id)
    delete_or_conflict(session, standard, "на профстандарт есть ссылки")


# --- ОТФ -------------------------------------------------------------------


@router.get("/general-functions", response_model=list[schemas.GeneralLaborFunctionOut])
def list_general_functions(session: SessionDep, standard_id: int | None = None):
    stmt = (
        select(models.GeneralLaborFunction)
        .order_by(models.GeneralLaborFunction.standard_id, models.GeneralLaborFunction.code)
        .options(
            selectinload(models.GeneralLaborFunction.functions).selectinload(
                models.LaborFunction.competencies
            )
        )
    )
    if standard_id is not None:
        stmt = stmt.where(models.GeneralLaborFunction.standard_id == standard_id)
    return session.scalars(stmt).all()


@router.post("/general-functions", response_model=schemas.GeneralLaborFunctionOut, status_code=201)
def create_general_function(data: schemas.GeneralLaborFunctionCreate, session: SessionDep):
    get_or_404(session, models.ProfStandard, data.standard_id)
    return save(session, models.GeneralLaborFunction(**data.model_dump()))


@router.put("/general-functions/{general_id}", response_model=schemas.GeneralLaborFunctionOut)
def update_general_function(
    general_id: int, data: schemas.GeneralLaborFunctionUpdate, session: SessionDep
):
    general = get_or_404(session, models.GeneralLaborFunction, general_id)
    return update_fields(session, general, data)


@router.delete("/general-functions/{general_id}", status_code=204)
def delete_general_function(general_id: int, session: SessionDep):
    """Удаляет ОТФ вместе с её ТФ."""
    general = get_or_404(session, models.GeneralLaborFunction, general_id)
    delete_or_conflict(session, general, "на ОТФ есть ссылки")


# --- ТФ --------------------------------------------------------------------


@router.get("/labor-functions", response_model=list[schemas.LaborFunctionOut])
def list_labor_functions(session: SessionDep, general_function_id: int | None = None):
    stmt = (
        select(models.LaborFunction)
        .order_by(models.LaborFunction.general_function_id, models.LaborFunction.code)
        .options(selectinload(models.LaborFunction.competencies))
    )
    if general_function_id is not None:
        stmt = stmt.where(models.LaborFunction.general_function_id == general_function_id)
    return session.scalars(stmt).all()


@router.post("/labor-functions", response_model=schemas.LaborFunctionOut, status_code=201)
def create_labor_function(data: schemas.LaborFunctionCreate, session: SessionDep):
    get_or_404(session, models.GeneralLaborFunction, data.general_function_id)
    return save(
        session,
        models.LaborFunction(
            general_function_id=data.general_function_id,
            code=data.code,
            name=data.name,
            competencies=get_many_or_404(session, models.Competency, data.competency_ids),
        ),
    )


@router.put("/labor-functions/{labor_function_id}", response_model=schemas.LaborFunctionOut)
def update_labor_function(
    labor_function_id: int, data: schemas.LaborFunctionIn, session: SessionDep
):
    """Меняет ТФ и её связь ТФ ⇒ компетенции."""
    labor_function = get_or_404(session, models.LaborFunction, labor_function_id)
    return update_fields(
        session,
        labor_function,
        code=data.code,
        name=data.name,
        competencies=get_many_or_404(session, models.Competency, data.competency_ids),
    )


@router.delete("/labor-functions/{labor_function_id}", status_code=204)
def delete_labor_function(labor_function_id: int, session: SessionDep):
    labor_function = get_or_404(session, models.LaborFunction, labor_function_id)
    delete_or_conflict(session, labor_function, "на ТФ есть ссылки")
