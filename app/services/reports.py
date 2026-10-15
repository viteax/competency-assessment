from collections import defaultdict

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.services import app_settings
from app.services.common import get_or_404


def _finished_attempts(student_ids: list[int], test_id: int | None):
    """Условия «завершённые попытки этих студентов (по тесту test_id, если задан)»."""
    conditions = [
        models.Attempt.student_id.in_(student_ids),
        models.Attempt.finished_at.is_not(None),
    ]
    if test_id is not None:
        conditions.append(
            models.Attempt.assignment_id.in_(
                select(models.Assignment.id).where(models.Assignment.test_id == test_id)
            )
        )
    return conditions


def _results_by_student(
    session: Session, student_ids: list[int], test_id: int | None = None
) -> dict[int, list[schemas.CompetencyResult]]:
    """Доля верных ответов по каждой компетенции в завершённых попытках (всех или одного
    теста) — для всех переданных студентов одним запросом, а не запросом на каждого."""
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
        .where(*_finished_attempts(student_ids, test_id))
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


def group_report(
    session: Session, group_id: int, test_id: int | None = None
) -> schemas.GroupCompetencyReport:
    group = get_or_404(session, models.Group, group_id)
    if test_id is not None:
        get_or_404(session, models.Test, test_id)
    students = sorted(group.students, key=lambda s: s.full_name)
    ids = [s.id for s in students]
    results = _results_by_student(session, ids, test_id)
    tested_at = dict(
        session.execute(
            select(models.Attempt.student_id, func.max(models.Attempt.finished_at))
            .where(*_finished_attempts(ids, test_id))
            .group_by(models.Attempt.student_id)
        ).all()
    )
    return schemas.GroupCompetencyReport(
        group_id=group.id,
        name=group.name,
        students=[
            schemas.StudentCompetencyReport(
                student_id=s.id,
                full_name=s.full_name,
                competencies=results[s.id],
                tested_at=tested_at.get(s.id),
            )
            for s in students
        ],
    )


def labor_functions(session: Session) -> list[models.LaborFunction]:
    """Все ТФ профстандартов с их компетенциями, по порядку кодов."""
    return session.scalars(
        select(models.LaborFunction)
        .join(models.GeneralLaborFunction)
        .join(models.ProfStandard)
        .order_by(models.ProfStandard.code, models.LaborFunction.code)
        .options(selectinload(models.LaborFunction.competencies))
    ).all()


def labor_function_axes(
    functions: list[models.LaborFunction], level: dict[int, float]
) -> list[schemas.ProfileAxis]:
    """Уровень ТФ — среднее уровней её проверенных компетенций (level: id компетенции → 0..1)."""
    axes = []
    for lf in functions:
        measured = [level[c.id] for c in lf.competencies if c.id in level]
        axes.append(
            schemas.ProfileAxis(
                code=lf.code,
                name=lf.name,
                value=round(sum(measured) / len(measured), 3) if measured else None,
                measured=len(measured),
                total=len(lf.competencies),
            )
        )
    return axes


def profile(
    session: Session, student_ids: list[int], test_id: int | None = None
) -> schemas.Profile:
    """Данные для «розы ветров»: уровень по каждой компетенции и трудовой функции (0..1).

    Для группы уровень компетенции — среднее по студентам, у которых она проверялась.
    Уровень ТФ — среднее по связанным с ней проверенным компетенциям; ТФ, у которой не
    проверена ни одна компетенция, получает value = None («нет данных»).
    """
    results = _results_by_student(session, student_ids, test_id)
    ratios: dict[int, list[float]] = defaultdict(list)
    names: dict[int, tuple[str, str]] = {}
    for rows in results.values():
        for r in rows:
            ratios[r.competency_id].append(r.ratio)
    for c in session.scalars(select(models.Competency).where(models.Competency.id.in_(ratios))):
        names[c.id] = (c.code, c.description)
    level = {cid: sum(v) / len(v) for cid, v in ratios.items()}

    tf_axes = labor_function_axes(labor_functions(session), level)
    return schemas.Profile(
        students=sum(bool(rows) for rows in results.values()),
        competencies=[
            schemas.ProfileAxis(
                code=names[cid][0],
                name=names[cid][1],
                value=round(level[cid], 3),
                measured=len(ratios[cid]),
                total=len(student_ids),
            )
            for cid in sorted(level, key=lambda cid: names[cid][0])
        ],
        labor_functions=tf_axes,
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
