"""Сборка тестов и назначение их группам (администратор)."""

from fastapi import APIRouter, Depends

from app import models, schemas
from app.api.deps import SessionDep, require_admin
from app.services import testing
from app.services.common import get_or_404

router = APIRouter(tags=["Тестирование"], dependencies=[Depends(require_admin)])


@router.post("/tests", response_model=schemas.TestOut, status_code=201)
def create_test(data: schemas.TestCreate, session: SessionDep):
    """Собирает тест: по `questions_per_competency` вопросов на каждую компетенцию."""
    return testing.create_test(session, data)


@router.get("/tests/{test_id}", response_model=schemas.TestOut)
def get_test(test_id: int, session: SessionDep):
    return get_or_404(session, models.Test, test_id)


@router.post("/assignments", response_model=schemas.AssignmentOut, status_code=201)
def assign_test(data: schemas.AssignmentIn, session: SessionDep):
    return testing.assign_test(session, data)
