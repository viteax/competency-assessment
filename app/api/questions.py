"""Банк вопросов. Администратор видит и правит все вопросы, преподаватель – только по своим
дисциплинам и их компетенциям."""

from fastapi import APIRouter, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.api.deps import SessionDep, StaffUser
from app.errors import Forbidden
from app.services import files, fund_import, questions, teaching
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
    direction_id: int | None = None,
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
    if direction_id is not None:
        stmt = stmt.join(models.Competency).where(models.Competency.direction_id == direction_id)
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


async def _fund_documents(
    file: UploadFile, user: models.User, discipline_id: int | None
) -> list[fund_import.FundDocument]:
    if user.role != models.Role.ADMIN and discipline_id is None:
        raise Forbidden("преподаватель загружает вопросы только в свою дисциплину")
    # На байт больше лимита – чтобы files.file_kind заметил слишком большой файл.
    filename, data = file.filename or "", await file.read(files.MAX_FILE_SIZE + 1)
    return [
        fund_import.parse(name, content) for name, content in fund_import.documents(filename, data)
    ]


@router.post("/questions/import/preview", response_model=schemas.FundPreview)
async def preview_fund(
    file: UploadFile,
    session: SessionDep,
    user: StaffUser,
    direction_id: int | None = Form(default=None),
    discipline_id: int | None = Form(default=None),
):
    """Разбирает ФОС дисциплины (.docx или .zip с несколькими): какие задания будут добавлены,
    какие уже есть в банке, какие не разобраны. Направление и дисциплина – из шапки документа;
    direction_id – направление, если в шапке нет его кода; discipline_id – загрузить в эту
    дисциплину (преподаватель – только в свою). В БД ничего не пишет."""
    docs = await _fund_documents(file, user, discipline_id)
    return fund_import.preview(session, docs, user, direction_id, discipline_id)


@router.post("/questions/import/apply", response_model=schemas.FundResult)
async def apply_fund(
    file: UploadFile,
    session: SessionDep,
    user: StaffUser,
    direction_id: int | None = Form(default=None),
    discipline_id: int | None = Form(default=None),
):
    """Добавляет новые задания из того же файла; дубли и неразобранные пропускает."""
    docs = await _fund_documents(file, user, discipline_id)
    return fund_import.apply(session, docs, user, direction_id, discipline_id)
