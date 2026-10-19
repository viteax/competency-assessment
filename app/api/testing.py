"""Сборка тестов и назначение их группам (администратор)."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.api.deps import SessionDep, require_admin
from app.api.files import DOCX, attachment
from app.services import curriculum, fund, testing

router = APIRouter(tags=["Тестирование"], dependencies=[Depends(require_admin)])


@router.post("/tests", response_model=schemas.TestOut, status_code=201)
def create_test(data: schemas.TestCreate, session: SessionDep):
    """Собирает тест: по `questions_per_competency` вопросов на каждую компетенцию."""
    return testing.create_test(session, data)


@router.get("/tests", response_model=list[schemas.TestOut])
def list_tests(session: SessionDep):
    return session.scalars(
        select(models.Test)
        .order_by(models.Test.created_at.desc())
        .options(selectinload(models.Test.test_questions), selectinload(models.Test.assignments))
    ).all()


@router.get("/tests/plan", response_model=schemas.AssemblyPlan)
def assembly_plan(group_id: int, session: SessionDep, semester: int | None = None):
    """Завершённые группой к семестру дисциплины (по умолчанию – к текущему) и сколько по ним
    вопросов в банке: из этого собирается тест на остаточные знания."""
    return curriculum.assembly_plan(session, group_id, semester)


@router.get("/tests/{test_id}", response_model=schemas.TestDetail)
def get_test(test_id: int, session: SessionDep):
    """Тест с вопросами по вариантам и назначениями группам."""
    return testing.test_detail(session, test_id)


@router.get("/tests/{test_id}/document.docx", response_class=Response)
def test_document(test_id: int, session: SessionDep, key: bool = False, variant: int | None = None):
    """Тест в Word по образцу ФОМ: бланк (поля «Ответ» пустые) или ключ (key=true).
    Без variant – все варианты, каждый с новой страницы."""
    content, filename = fund.test_document(session, test_id, key, variant)
    return attachment(content, filename, DOCX)


@router.delete("/tests/{test_id}", status_code=204)
def delete_test(test_id: int, session: SessionDep):
    testing.delete_test(session, test_id)


@router.post("/assignments", response_model=schemas.AssignmentOut, status_code=201)
def assign_test(data: schemas.AssignmentIn, session: SessionDep):
    return testing.assign_test(session, data)


@router.delete("/assignments/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: int, session: SessionDep):
    testing.delete_assignment(session, assignment_id)
