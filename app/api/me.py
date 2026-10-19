"""Личный кабинет студента: назначенные тесты, прохождение, свои результаты."""

from fastapi import APIRouter

from app import schemas
from app.api.deps import CurrentStudent, SessionDep
from app.services import reports, testing

router = APIRouter(prefix="/me", tags=["Студент"])


@router.get("/assignments", response_model=list[schemas.StudentAssignmentOut])
def my_assignments(student: CurrentStudent, session: SessionDep):
    """Назначенные группе тесты и состояние моей попытки по каждому."""
    return testing.student_assignments(session, student)


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
