"""Данные для выгрузки в Word: собранный тест (по вариантам) и ФОМ дисциплины."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.errors import NotFound
from app.services.common import code_key, get_or_404
from app.services.word_export import FundHeader, Section, build

_QUESTION_LOAD = (
    selectinload(models.Question.options),
    selectinload(models.Question.competency),
    selectinload(models.Question.discipline),
)


def _directions_and_semesters(session: Session, discipline_ids: list[int]) -> tuple[str, str]:
    entries = session.scalars(
        select(models.CurriculumEntry)
        .where(models.CurriculumEntry.discipline_id.in_(discipline_ids))
        .options(selectinload(models.CurriculumEntry.direction))
    ).all()
    directions = sorted({f"{e.direction.code} {e.direction.name}" for e in entries})
    semesters = sorted({e.last_semester for e in entries})
    return "\n".join(directions), ", ".join(map(str, semesters))


def _sections(questions: list[models.Question]) -> list[Section]:
    """Задания по компетенциям (компетенции – по коду), внутри – в исходном порядке."""
    by_competency: dict[int, list[models.Question]] = defaultdict(list)
    for q in questions:
        by_competency[q.competency_id].append(q)
    groups = sorted(by_competency.values(), key=lambda qs: code_key(qs[0].competency.code))
    return [Section(competency=qs[0].competency, questions=qs) for qs in groups]


def _filename(name: str, key: bool) -> str:
    safe = "".join(ch for ch in name if ch not in '\\/:*?"<>|').strip() or "задания"
    return f"{safe} – ключ.docx" if key else f"{safe}.docx"


def test_document(
    session: Session, test_id: int, key: bool, variant: int | None = None
) -> tuple[bytes, str]:
    """Тест в Word: каждый вариант – с новой страницы (или только выбранный)."""
    test = session.scalar(
        select(models.Test)
        .where(models.Test.id == test_id)
        .options(
            selectinload(models.Test.disciplines),
            selectinload(models.Test.test_questions)
            .selectinload(models.TestQuestion.question)
            .options(*_QUESTION_LOAD),
        )
    )
    if test is None:
        raise NotFound(f"Test {test_id} не найден")
    variants: dict[int, list[models.Question]] = defaultdict(list)
    for tq in test.test_questions:
        variants[tq.variant].append(tq.question)
    if variant is not None and variant not in variants:
        raise NotFound(f"в тесте нет варианта {variant}")

    disciplines = test.disciplines or sorted(
        {q.discipline for qs in variants.values() for q in qs if q.discipline},
        key=lambda d: d.name,
    )
    directions, semesters = _directions_and_semesters(session, [d.id for d in disciplines])
    semester = str(test.semester) if test.semester else semesters
    parts = []
    for number in sorted(variants) if variant is None else [variant]:
        sections = _sections(variants[number])
        header = FundHeader(
            directions=directions,
            semester=semester,
            discipline=", ".join(d.name for d in disciplines),
            competencies=[s.competency for s in sections],
        )
        title = f"«{test.title}», вариант {number}" if len(variants) > 1 else f"«{test.title}»"
        parts.append((header, sections, title))
    suffix = f", вариант {variant}" if variant is not None and len(variants) > 1 else ""
    return build(parts, key), _filename(f"{test.title}{suffix}", key)


def discipline_document(session: Session, discipline_id: int, key: bool) -> tuple[bytes, str]:
    """ФОМ дисциплины: все её вопросы из банка, по компетенциям."""
    discipline = get_or_404(session, models.Discipline, discipline_id)
    questions = session.scalars(
        select(models.Question)
        .where(models.Question.discipline_id == discipline.id)
        .order_by(models.Question.id)
        .options(*_QUESTION_LOAD)
    ).all()
    if not questions:
        raise NotFound(f"в банке нет вопросов по дисциплине «{discipline.name}»")
    sections = _sections(list(questions))
    directions, semesters = _directions_and_semesters(session, [discipline.id])
    header = FundHeader(
        directions=directions,
        semester=semesters,
        discipline=discipline.name,
        competencies=[s.competency for s in sections],
    )
    return build([(header, sections, "")], key), _filename(f"ФОМ – {discipline.name}", key)
