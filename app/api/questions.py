"""Банк вопросов. Администратор видит и правит все вопросы, преподаватель – только по своим
дисциплинам и их компетенциям."""

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.api.deps import SessionDep, StaffUser
from app.services import questions, teaching
from app.services.common import get_or_404

router = APIRouter(tags=["Банк вопросов"])


@router.post("/questions", response_model=schemas.QuestionOut, status_code=201)
def create_question(data: schemas.QuestionIn, session: SessionDep, user: StaffUser):
    teaching.check_question_access(session, user, data.discipline_id, data.competency_id)
    return questions.create_question(session, data)


@router.get("/questions", response_model=list[schemas.QuestionOut])
def list_questions(
    session: SessionDep,
    user: StaffUser,
    competency_id: int | None = None,
    discipline_id: int | None = None,
):
    stmt = (
        select(models.Question)
        .order_by(models.Question.id)
        .options(selectinload(models.Question.options), selectinload(models.Question.test_links))
    )
    if competency_id is not None:
        stmt = stmt.where(models.Question.competency_id == competency_id)
    if discipline_id is not None:
        stmt = stmt.where(models.Question.discipline_id == discipline_id)
    if user.role == models.Role.TEACHER:
        own = teaching.discipline_ids_of(session, user)
        stmt = stmt.where(models.Question.discipline_id.in_(own))
    return session.scalars(stmt).all()


@router.put("/questions/{question_id}", response_model=schemas.QuestionOut)
def update_question(
    question_id: int, data: schemas.QuestionUpdate, session: SessionDep, user: StaffUser
):
    question = get_or_404(session, models.Question, question_id)
    teaching.check_question_access(session, user, question.discipline_id, question.competency_id)
    teaching.check_question_access(session, user, data.discipline_id, data.competency_id)
    return questions.update_question(session, question, data)


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(question_id: int, session: SessionDep, user: StaffUser):
    question = get_or_404(session, models.Question, question_id)
    teaching.check_question_access(session, user, question.discipline_id, question.competency_id)
    questions.delete_question(session, question)
