"""Учебный план и подбор дисциплин для оценки остаточных знаний."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.errors import Conflict, DomainError
from app.services.common import get_or_404, save


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
                kind=e.discipline.kind,
                first_semester=e.first_semester,
                last_semester=e.last_semester,
                competency_ids=e.discipline.competency_ids,
            )
            for e in entries
        ),
        key=lambda d: (d.last_semester, d.name),
    )
    finished = [d for d in planned if d.last_semester < semester]
    # Дисциплины направления, у которых семестры не указаны в учебном плане.
    unplanned = session.scalars(
        select(models.Discipline.name)
        .where(
            models.Discipline.direction_id == group.direction_id,
            models.Discipline.id.not_in(select(models.CurriculumEntry.discipline_id)),
        )
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


def save_entry(
    session: Session, entry: models.CurriculumEntry, data: schemas.CurriculumEntryIn
) -> models.CurriculumEntry:
    """Сохраняет строку учебного плана: направление – направление дисциплины, преподаватель –
    только с ролью «преподаватель», квоты – только по компетенциям дисциплины, по одной на
    компетенцию. У дисциплины одна строка плана."""
    discipline = get_or_404(session, models.Discipline, data.discipline_id)
    other = session.scalar(
        select(models.CurriculumEntry.id).where(
            models.CurriculumEntry.discipline_id == discipline.id
        )
    )
    if other is not None and other != entry.id:
        raise Conflict(f"«{discipline.name}» уже есть в учебном плане – измените ту строку")
    if data.teacher_id is not None:
        teacher = get_or_404(session, models.User, data.teacher_id)
        if teacher.role != models.Role.TEACHER:
            raise DomainError("закрепить дисциплину можно только за преподавателем")
    allowed = set(discipline.competency_ids)
    if any(q.competency_id not in allowed for q in data.quotas):
        raise DomainError(f"квота задана для компетенции, которую «{discipline.name}» не формирует")
    if len({q.competency_id for q in data.quotas}) != len(data.quotas):
        raise DomainError("у одной компетенции может быть только одна квота")
    if entry.id is not None:
        entry.quotas = []
        session.flush()  # старые квоты удаляются до вставки новых с тем же ключом
    for field in ("discipline_id", "first_semester", "last_semester", "teacher_id"):
        setattr(entry, field, getattr(data, field))
    entry.direction_id = discipline.direction_id
    entry.quotas = [
        models.CurriculumQuota(competency_id=q.competency_id, questions=q.questions)
        for q in data.quotas
    ]
    return save(session, entry)
