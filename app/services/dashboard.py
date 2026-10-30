"""Главная страница администратора: общая картина и что требует внимания."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.services.common import code_key
from app.services.teaching import entries_progress

RECENT_ASSIGNMENTS = 5


def _names(items: list[str], limit: int = 4) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" и ещё {len(items) - limit}" if len(items) > limit else "")


def dashboard(session: Session) -> schemas.Dashboard:
    def count(model) -> int:
        return session.scalar(select(func.count()).select_from(model))

    students = count(models.Student)
    with_account = session.scalar(
        select(func.count()).select_from(models.User).where(models.User.student_id.is_not(None))
    )
    counts = schemas.DashboardCounts(
        groups=count(models.Group),
        students=students,
        students_with_account=with_account,
        teachers=session.scalar(
            select(func.count())
            .select_from(models.User)
            .where(models.User.role == models.Role.TEACHER)
        ),
        questions=count(models.Question),
        tests=count(models.Test),
    )

    entries = list(
        session.scalars(
            select(models.CurriculumEntry).options(
                selectinload(models.CurriculumEntry.discipline).selectinload(
                    models.Discipline.competencies
                ),
                selectinload(models.CurriculumEntry.direction),
                selectinload(models.CurriculumEntry.quotas),
                selectinload(models.CurriculumEntry.teacher),
            )
        )
    )
    with_teacher = [e for e in entries if e.teacher_id is not None]
    teacher_of = {e.id: e.teacher.full_name or e.teacher.username for e in with_teacher}
    teachers = [
        schemas.TeacherProgress(
            teacher=teacher_of[p.entry_id],
            discipline=p.discipline,
            discipline_id=p.discipline_id,
            required=p.required,
            done=p.done,
        )
        for p in entries_progress(session, with_teacher)
    ]

    return schemas.Dashboard(
        counts=counts,
        teachers=sorted(teachers, key=lambda t: (t.done >= t.required, t.teacher, t.discipline)),
        assignments=_recent_assignments(session),
        attention=_attention(session, entries, counts),
    )


def _recent_assignments(session: Session) -> list[schemas.AssignmentProgress]:
    assignments = session.scalars(
        select(models.Assignment)
        .order_by(models.Assignment.created_at.desc(), models.Assignment.id.desc())
        .limit(RECENT_ASSIGNMENTS)
        .options(selectinload(models.Assignment.test), selectinload(models.Assignment.group))
    ).all()
    finished = dict(
        session.execute(
            select(models.Attempt.assignment_id, func.count())
            .where(
                models.Attempt.assignment_id.in_([a.id for a in assignments]),
                models.Attempt.finished_at.is_not(None),
            )
            .group_by(models.Attempt.assignment_id)
        ).all()
    )
    sizes = dict(
        session.execute(
            select(models.Student.group_id, func.count()).group_by(models.Student.group_id)
        ).all()
    )
    return [
        schemas.AssignmentProgress(
            test_id=a.test_id,
            test=a.test.title,
            group_id=a.group_id,
            group=a.group.name,
            assigned_at=a.created_at,
            students=sizes.get(a.group_id, 0),
            finished=finished.get(a.id, 0),
        )
        for a in assignments
    ]


def _attention(
    session: Session, entries: list[models.CurriculumEntry], counts: schemas.DashboardCounts
) -> list[schemas.AttentionItem]:
    items: list[schemas.AttentionItem] = []

    def add(text: str, target: schemas.Target) -> None:
        items.append(schemas.AttentionItem(text=text, target=target))

    # При нескольких планах одинаковые названия и коды различаются подписью плана.
    several = len({e.direction_id for e in entries}) > 1

    def label(e: models.CurriculumEntry) -> str:
        return f"{e.discipline.name} ({e.direction.label})" if several else e.discipline.name

    no_teacher = sorted({label(e) for e in entries if e.teacher_id is None})
    if no_teacher:
        add(f"Не закреплены за преподавателем: {_names(no_teacher)}", "curriculum")
    no_quotas = sorted({label(e) for e in entries if e.teacher_id and not e.quotas})
    if no_quotas:
        add(f"Не задано, сколько вопросов разработать: {_names(no_quotas)}", "curriculum")

    no_year = list(
        session.scalars(
            select(models.Group.name)
            .where(models.Group.start_year.is_(None))
            .order_by(models.Group.name)
        )
    )
    if no_year:
        add(
            f"Не указан год набора (не считается семестр): {_names(no_year)}",
            "groups",
        )

    rows = session.execute(
        select(models.Competency.code, models.Direction)
        .join(models.Direction)
        .where(~models.Competency.id.in_(select(models.Question.competency_id)))
    ).all()
    several = len({direction.id for _, direction in rows}) > 1
    empty = [
        f"{code} ({direction.label})" if several else code
        for code, direction in sorted(rows, key=lambda r: (r[1].label, code_key(r[0])))
    ]
    if empty:
        add(f"Компетенции без вопросов в банке: {_names(empty)}", "bank")

    unlinked = list(
        session.scalars(
            select(models.LaborFunction.code)
            .where(~models.LaborFunction.competencies.any())
            .order_by(models.LaborFunction.code)
        )
    )
    if unlinked:
        add(f"Трудовые функции без компетенций: {_names(unlinked)}", "labor_functions")

    without = counts.students - counts.students_with_account
    if without:
        add(
            f"Студентов без учётной записи: {without}. Они могут зарегистрироваться сами "
            "на странице входа по ФИО.",
            "students",
        )
    if not counts.tests:
        add("Тестов пока нет – соберите первый тест.", "tests")
    return items
