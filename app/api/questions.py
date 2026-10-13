"""Банк вопросов."""

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.api.deps import SessionDep
from app.errors import DomainError
from app.services.common import get_or_404

router = APIRouter(tags=["Банк вопросов"])


@router.post("/questions", response_model=schemas.QuestionOut, status_code=201)
def create_question(data: schemas.QuestionIn, session: SessionDep):
    get_or_404(session, models.Competency, data.competency_id)
    if data.indicator_id is not None:
        indicator = get_or_404(session, models.Indicator, data.indicator_id)
        if indicator.competency_id != data.competency_id:
            raise DomainError("индикатор относится к другой компетенции")
    if data.discipline_id is not None:
        get_or_404(session, models.Discipline, data.discipline_id)
    question = models.Question(
        competency_id=data.competency_id,
        indicator_id=data.indicator_id,
        discipline_id=data.discipline_id,
        text=data.text,
        options=[models.AnswerOption(**o.model_dump()) for o in data.options],
    )
    session.add(question)
    session.commit()
    return question


@router.get("/questions", response_model=list[schemas.QuestionOut])
def list_questions(
    session: SessionDep,
    competency_id: int | None = None,
    discipline_id: int | None = None,
):
    stmt = (
        select(models.Question)
        .order_by(models.Question.id)
        .options(selectinload(models.Question.options))
    )
    if competency_id is not None:
        stmt = stmt.where(models.Question.competency_id == competency_id)
    if discipline_id is not None:
        stmt = stmt.where(models.Question.discipline_id == discipline_id)
    return session.scalars(stmt).all()
