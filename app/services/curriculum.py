"""Учебный план и подбор дисциплин для оценки остаточных знаний."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.errors import DomainError
from app.services.common import get_or_404


def assembly_plan(
    session: Session, group_id: int, semester: int | None = None
) -> schemas.AssemblyPlan:
    """Дисциплины направления группы, завершённые до семестра `semester` (по умолчанию –
    текущего), и сколько по ним вопросов в банке.

    Остаточные знания проверяют только по завершённым дисциплинам: во 2-м семестре нельзя
    брать математику, которая идёт в 1–2 семестрах, – её ещё изучают.
    """
    group = get_or_404(session, models.Group, group_id)
    semester = semester or group.current_semester
    if semester is None:
        raise DomainError(
            f"у группы {group.name} не указан год набора – укажите его или выберите семестр"
        )
    entries = session.scalars(
        select(models.CurriculumEntry)
        .where(models.CurriculumEntry.direction_id == group.direction_id)
        .options(
            selectinload(models.CurriculumEntry.discipline).selectinload(
                models.Discipline.competencies
            )
        )
    ).all()
    planned = sorted(
        (
            schemas.PlanDiscipline(
                id=e.discipline.id,
                name=e.discipline.name,
                first_semester=e.first_semester,
                last_semester=e.last_semester,
                competency_ids=e.discipline.competency_ids,
            )
            for e in entries
        ),
        key=lambda d: (d.last_semester, d.name),
    )
    finished = [d for d in planned if d.last_semester < semester]
    # Дисциплины, у которых семестры не указаны ни в одном учебном плане (дисциплины других
    # направлений сюда не попадают).
    unplanned = session.scalars(
        select(models.Discipline.name)
        .where(models.Discipline.id.not_in(select(models.CurriculumEntry.discipline_id)))
        .order_by(models.Discipline.name)
    ).all()

    counts = session.execute(
        select(models.Question.competency_id, models.Question.discipline_id, func.count())
        .where(models.Question.discipline_id.in_([d.id for d in finished]))
        .group_by(models.Question.competency_id, models.Question.discipline_id)
    ).all()
    return schemas.AssemblyPlan(
        group_id=group.id,
        semester=semester,
        finished=finished,
        not_finished=[d for d in planned if d.last_semester >= semester],
        unplanned=list(unplanned),
        question_counts=[
            schemas.QuestionCount(competency_id=c, discipline_id=d, count=n) for c, d, n in counts
        ],
    )
