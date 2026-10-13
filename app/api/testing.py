"""Сборка тестов, назначение группам, прохождение."""

from fastapi import APIRouter

from app import models, schemas
from app.api.deps import SessionDep
from app.services import testing
from app.services.common import get_or_404

router = APIRouter(tags=["Тестирование"])


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


@router.post("/attempts", response_model=schemas.AttemptStarted, status_code=201)
def start_attempt(data: schemas.AttemptStart, session: SessionDep):
    attempt, questions = testing.start_attempt(session, data)
    return schemas.AttemptStarted(
        attempt_id=attempt.id,
        title=attempt.assignment.test.title,
        questions=[schemas.StudentQuestionOut.model_validate(q) for q in questions],
    )


@router.post("/attempts/{attempt_id}/submit", response_model=schemas.AttemptResult)
def submit_attempt(attempt_id: int, data: schemas.AttemptSubmit, session: SessionDep):
    attempt = testing.submit_attempt(session, attempt_id, data)
    return schemas.AttemptResult(
        attempt_id=attempt.id,
        score=attempt.score,
        max_score=attempt.max_score,
        finished_at=attempt.finished_at,
    )
