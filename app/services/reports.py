from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.services import app_settings
from app.services.common import get_or_404


def _results_by_student(
    session: Session, student_ids: list[int]
) -> dict[int, list[schemas.CompetencyResult]]:
    """Доля верных ответов по каждой компетенции во всех завершённых попытках — для всех
    переданных студентов одним запросом (отчёт по группе не делает запрос на каждого)."""
    threshold = app_settings.mastery_threshold(session)
    stmt = (
        select(
            models.Attempt.student_id,
            models.Competency,
            func.sum(cast(models.AttemptAnswer.is_correct, Integer)),
            func.count(),
        )
        .join(models.Question, models.Question.competency_id == models.Competency.id)
        .join(models.AttemptAnswer, models.AttemptAnswer.question_id == models.Question.id)
        .join(models.Attempt, models.Attempt.id == models.AttemptAnswer.attempt_id)
        .where(models.Attempt.student_id.in_(student_ids), models.Attempt.finished_at.is_not(None))
        .group_by(models.Attempt.student_id, models.Competency.id)
        .order_by(models.Competency.code)
    )
    results: dict[int, list[schemas.CompetencyResult]] = {sid: [] for sid in student_ids}
    for student_id, competency, correct, total in session.execute(stmt):
        ratio = correct / total
        results[student_id].append(
            schemas.CompetencyResult(
                competency_id=competency.id,
                code=competency.code,
                kind=competency.kind,
                correct=correct,
                total=total,
                ratio=round(ratio, 3),
                mastered=ratio >= threshold,
            )
        )
    return results


def competency_results(session: Session, student_id: int) -> list[schemas.CompetencyResult]:
    return _results_by_student(session, [student_id])[student_id]


def student_report(session: Session, student_id: int) -> schemas.StudentCompetencyReport:
    student = get_or_404(session, models.Student, student_id)
    return schemas.StudentCompetencyReport(
        student_id=student.id,
        full_name=student.full_name,
        competencies=competency_results(session, student.id),
    )


def group_report(session: Session, group_id: int) -> schemas.GroupCompetencyReport:
    group = get_or_404(session, models.Group, group_id)
    students = sorted(group.students, key=lambda s: s.full_name)
    results = _results_by_student(session, [s.id for s in students])
    return schemas.GroupCompetencyReport(
        group_id=group.id,
        name=group.name,
        students=[
            schemas.StudentCompetencyReport(
                student_id=s.id, full_name=s.full_name, competencies=results[s.id]
            )
            for s in students
        ],
    )


def labor_function_report(
    session: Session, student_id: int
) -> list[schemas.GeneralLaborFunctionResult]:
    """ПК → ОТФ: какие трудовые функции профстандарта закрывает студент.

    ТФ считается закрытой, если все связанные с ней компетенции сформированы.
    ОТФ закрыта, если закрыты все её ТФ.
    """
    get_or_404(session, models.Student, student_id)
    mastered = {r.competency_id for r in competency_results(session, student_id) if r.mastered}

    generals = session.scalars(
        select(models.GeneralLaborFunction)
        .join(models.ProfStandard)
        .order_by(models.ProfStandard.code, models.GeneralLaborFunction.code)
        .options(
            selectinload(models.GeneralLaborFunction.standard),
            selectinload(models.GeneralLaborFunction.functions).selectinload(
                models.LaborFunction.competencies
            ),
        )
    )
    report = []
    for general in generals:
        functions = []
        for lf in sorted(general.functions, key=lambda f: f.code):
            required = {c.id for c in lf.competencies}
            functions.append(
                schemas.LaborFunctionResult(
                    labor_function_id=lf.id,
                    code=lf.code,
                    name=lf.name,
                    competency_codes=sorted(c.code for c in lf.competencies),
                    covered=bool(required) and required <= mastered,
                )
            )
        report.append(
            schemas.GeneralLaborFunctionResult(
                standard_code=general.standard.code,
                code=general.code,
                name=general.name,
                functions=functions,
                covered=bool(functions) and all(f.covered for f in functions),
            )
        )
    return report
