"""Личный кабинет студента: назначенные тесты, прохождение, свои результаты."""

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.api.deps import CurrentStudent, SessionDep
from app.services import reports, testing

router = APIRouter(prefix="/me", tags=["Студент"])


@router.get("/assignments", response_model=list[schemas.StudentAssignmentOut])
def my_assignments(student: CurrentStudent, session: SessionDep):
    """Назначенные группе тесты и состояние моей попытки по каждому."""
    assignments = session.scalars(
        select(models.Assignment)
        .where(models.Assignment.group_id == student.group_id)
        .order_by(models.Assignment.created_at.desc())
        .options(selectinload(models.Assignment.test).selectinload(models.Test.test_questions))
    ).all()
    attempts = {
        a.assignment_id: a
        for a in session.scalars(
            select(models.Attempt).where(
                models.Attempt.student_id == student.id,
                models.Attempt.assignment_id.in_([a.id for a in assignments]),
            )
        )
    }
    return [
        schemas.StudentAssignmentOut(
            id=a.id,
            title=a.test.title,
            question_count=a.test.questions_per_variant,
            created_at=a.created_at,
            attempt=attempts.get(a.id),
        )
        for a in assignments
    ]


@router.post("/attempts", response_model=schemas.AttemptStarted, status_code=201)
def start_attempt(data: schemas.AttemptStart, student: CurrentStudent, session: SessionDep):
    attempt, questions = testing.start_attempt(session, data.assignment_id, student)
    return schemas.AttemptStarted(
        attempt_id=attempt.id,
        title=attempt.assignment.test.title,
        questions=questions,
    )


@router.post("/attempts/{attempt_id}/submit", response_model=schemas.AttemptResult)
def submit_attempt(
    attempt_id: int, data: schemas.AttemptSubmit, student: CurrentStudent, session: SessionDep
):
    attempt = testing.submit_attempt(session, attempt_id, student, data)
    return schemas.AttemptResult(
        attempt_id=attempt.id,
        score=attempt.score,
        max_score=attempt.max_score,
        finished_at=attempt.finished_at,
        competencies=reports.attempt_results(session, attempt),
    )


@router.get("/reports/competencies", response_model=schemas.StudentCompetencyReport)
def my_competencies(student: CurrentStudent, session: SessionDep):
    return reports.student_report(session, student.id)


@router.get("/reports/labor-functions", response_model=list[schemas.GeneralLaborFunctionResult])
def my_labor_functions(student: CurrentStudent, session: SessionDep):
    return reports.labor_function_report(session, student.id)


@router.get("/reports/profile", response_model=schemas.Profile)
def my_profile(student: CurrentStudent, session: SessionDep):
    """Мои уровни по компетенциям и трудовым функциям – для «розы ветров»."""
    result = reports.profile(session, [student.id])
    result.legend = reports.student_legend(student)
    return result
