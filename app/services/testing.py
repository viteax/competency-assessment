import random
from collections import Counter, defaultdict
from itertools import zip_longest

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.errors import Conflict, DomainError, NotFound
from app.services.common import get_many_or_404, get_or_404, save


def pick_questions(
    questions: list[models.Question], count: int, rng: random.Random
) -> list[models.Question]:
    """Выбирает `count` вопросов, равномерно распределяя их по индикаторам компетенции."""
    by_indicator: dict[int | None, list[models.Question]] = defaultdict(list)
    for q in questions:
        by_indicator[q.indicator_id].append(q)
    buckets = list(by_indicator.values())
    for bucket in buckets:
        rng.shuffle(bucket)
    rng.shuffle(buckets)
    # По одному вопросу из каждого индикатора по кругу: 1.1, 1.2, 1.3, 1.1, 1.2, ...
    interleaved = [q for round_ in zip_longest(*buckets) for q in round_ if q is not None]
    return interleaved[:count]


def title_key(title: str) -> str:
    return " ".join(title.split()).casefold()


def ensure_unique_title(session: Session, title: str) -> None:
    """Название теста уникально без учёта регистра и лишних пробелов: «Входной контроль»
    и «входной  контроль» в списках и отчётах не различить.

    Сравниваем в Python: lower() в SQLite не работает с кириллицей, а тестов немного.
    """
    key = title_key(title)
    if any(title_key(t) == key for t in session.scalars(select(models.Test.title))):
        raise Conflict(
            f"тест «{title}» уже есть — выберите другое название или назначьте существующий тест"
        )


def create_test(
    session: Session, data: schemas.TestCreate, rng: random.Random | None = None
) -> models.Test:
    """Собирает тест в нескольких вариантах, которые не пересекаются по вопросам.

    По каждой компетенции нужно k = questions_per_competency вопросов на вариант; вариантов
    столько, на сколько хватает вопросов самой «бедной» компетенции: 20 вопросов при k = 5 —
    4 варианта. Внутри варианта вопросы распределены по индикаторам компетенции.
    """
    rng = rng or random.Random()
    ensure_unique_title(session, data.title)
    disciplines = get_many_or_404(session, models.Discipline, data.discipline_ids)
    competencies = get_many_or_404(session, models.Competency, data.competency_ids)
    k = data.questions_per_competency

    pools: list[list[models.Question]] = []
    for competency in competencies:
        stmt = select(models.Question).where(models.Question.competency_id == competency.id)
        if disciplines:
            stmt = stmt.where(models.Question.discipline_id.in_([d.id for d in disciplines]))
        pools.append(list(session.scalars(stmt)))
    short = [
        f"{c.code} — {len(pool)} из {k}"
        for c, pool in zip(competencies, pools, strict=True)
        if len(pool) < k
    ]
    if short:
        where = " в выбранных дисциплинах" if disciplines else ""
        raise DomainError(f"не хватает вопросов{where}: {', '.join(short)}")

    variant_count = min(len(pool) // k for pool in pools)
    variants: list[list[models.Question]] = [[] for _ in range(variant_count)]
    for pool in pools:
        ordered = pick_questions(pool, variant_count * k, rng)
        for v in range(variant_count):
            variants[v].extend(ordered[v * k : (v + 1) * k])

    test = models.Test(title=data.title, semester=data.semester, disciplines=disciplines)
    test.test_questions = [
        models.TestQuestion(question=q, variant=v, position=i)
        for v, questions in enumerate(variants, start=1)
        for i, q in enumerate(questions)
    ]
    return save(session, test)


def delete_test(session: Session, test_id: int) -> None:
    """Удаляет тест вместе с назначениями, если его ещё никто не открывал."""
    test = get_or_404(session, models.Test, test_id)
    if session.scalar(
        select(models.Attempt.id)
        .join(models.Assignment)
        .where(models.Assignment.test_id == test.id)
        .limit(1)
    ):
        raise Conflict("тест уже проходили — удалить его нельзя, иначе пропадут результаты")
    for assignment in test.assignments:
        session.delete(assignment)
    session.delete(test)
    session.commit()


def delete_assignment(session: Session, assignment_id: int) -> None:
    assignment = get_or_404(session, models.Assignment, assignment_id)
    if session.scalar(
        select(models.Attempt.id).where(models.Attempt.assignment_id == assignment.id).limit(1)
    ):
        raise Conflict("группа уже проходит этот тест — снять назначение нельзя")
    session.delete(assignment)
    session.commit()


def assign_test(session: Session, data: schemas.AssignmentIn) -> models.Assignment:
    get_or_404(session, models.Test, data.test_id)
    get_or_404(session, models.Group, data.group_id)
    exists = session.scalar(
        select(models.Assignment).where(
            models.Assignment.test_id == data.test_id,
            models.Assignment.group_id == data.group_id,
        )
    )
    if exists:
        raise Conflict("тест уже назначен этой группе")
    assignment = models.Assignment(test_id=data.test_id, group_id=data.group_id)
    return save(session, assignment)


def _test_questions(session: Session, test_id: int, variant: int) -> list[models.Question]:
    rows = session.scalars(
        select(models.TestQuestion)
        .where(models.TestQuestion.test_id == test_id, models.TestQuestion.variant == variant)
        .order_by(models.TestQuestion.position)
        .options(selectinload(models.TestQuestion.question).selectinload(models.Question.options))
    )
    return [tq.question for tq in rows]


def _choose_variant(session: Session, assignment: models.Assignment) -> int:
    """Случайный вариант из наименее выданных в этом назначении: соседи по аудитории
    получают разные варианты, пока они не закончатся."""
    variants = session.scalars(
        select(models.TestQuestion.variant)
        .where(models.TestQuestion.test_id == assignment.test_id)
        .distinct()
    ).all()
    issued = Counter(
        session.scalars(
            select(models.Attempt.variant).where(models.Attempt.assignment_id == assignment.id)
        )
    )
    least = min(issued[v] for v in variants)
    return random.choice([v for v in variants if issued[v] == least])


def _shuffled_for(attempt: models.Attempt, questions: list[models.Question]):
    """Порядок вопросов и вариантов ответа у каждого студента свой, но при повторном
    открытии теста тот же (зависит от номера попытки)."""
    rng = random.Random(attempt.id)
    result = [schemas.StudentQuestionOut.model_validate(q) for q in questions]
    rng.shuffle(result)
    for q in result:
        rng.shuffle(q.options)
    return result


def start_attempt(
    session: Session, assignment_id: int, student: models.Student
) -> tuple[models.Attempt, list[schemas.StudentQuestionOut]]:
    assignment = session.get(models.Assignment, assignment_id)
    # Чужие назначения не отличаем от несуществующих.
    if assignment is None or assignment.group_id != student.group_id:
        raise NotFound(f"назначение {assignment_id} не найдено")

    attempt = session.scalar(
        select(models.Attempt).where(
            models.Attempt.assignment_id == assignment.id,
            models.Attempt.student_id == student.id,
        )
    )
    if attempt is not None and attempt.finished_at is not None:
        raise Conflict("тест уже пройден")
    if attempt is None:
        attempt = save(
            session,
            models.Attempt(
                assignment_id=assignment.id,
                student_id=student.id,
                variant=_choose_variant(session, assignment),
            ),
        )
    questions = _test_questions(session, assignment.test_id, attempt.variant)
    return attempt, _shuffled_for(attempt, questions)


def submit_attempt(
    session: Session, attempt_id: int, student: models.Student, data: schemas.AttemptSubmit
) -> models.Attempt:
    attempt = session.get(models.Attempt, attempt_id)
    if attempt is None or attempt.student_id != student.id:
        raise NotFound(f"попытка {attempt_id} не найдена")
    if attempt.finished_at is not None:
        raise Conflict("попытка уже завершена")

    questions = {
        q.id: q for q in _test_questions(session, attempt.assignment.test_id, attempt.variant)
    }
    chosen: dict[int, int] = {}
    for answer in data.answers:
        question = questions.get(answer.question_id)
        if question is None:
            raise NotFound(f"вопроса {answer.question_id} нет в этом тесте")
        if answer.question_id in chosen:
            raise DomainError(f"на вопрос {answer.question_id} дано несколько ответов")
        if answer.option_id not in {o.id for o in question.options}:
            raise DomainError(f"вариант {answer.option_id} не относится к вопросу {question.id}")
        chosen[answer.question_id] = answer.option_id

    # Вопросы без ответа засчитываются как неверные.
    attempt.answers = []
    score = 0
    for question in questions.values():
        option_id = chosen.get(question.id)
        correct = any(o.id == option_id and o.is_correct for o in question.options)
        score += correct
        attempt.answers.append(
            models.AttemptAnswer(question_id=question.id, option_id=option_id, is_correct=correct)
        )
    attempt.score = score
    attempt.max_score = len(questions)
    attempt.finished_at = models.utcnow()
    session.commit()
    return attempt


def test_detail(session: Session, test_id: int) -> schemas.TestDetail:
    test = session.scalar(
        select(models.Test)
        .where(models.Test.id == test_id)
        .options(
            selectinload(models.Test.test_questions)
            .selectinload(models.TestQuestion.question)
            .selectinload(models.Question.options),
            selectinload(models.Test.assignments).selectinload(models.Assignment.group),
        )
    )
    if test is None:
        raise NotFound(f"Test {test_id} не найден")
    by_variant: dict[int, list[models.Question]] = defaultdict(list)
    for tq in test.test_questions:  # уже по порядку position
        by_variant[tq.variant].append(tq.question)

    progress = {
        assignment_id: (started, finished)
        for assignment_id, started, finished in session.execute(
            select(
                models.Attempt.assignment_id,
                func.count(),
                func.count(models.Attempt.finished_at),
            )
            .where(models.Attempt.assignment_id.in_([a.id for a in test.assignments]))
            .group_by(models.Attempt.assignment_id)
        )
    }
    return schemas.TestDetail.model_validate(
        {
            **schemas.TestOut.model_validate(test).model_dump(),
            "variants": [
                {"variant": v, "questions": questions}
                for v, questions in sorted(by_variant.items())
            ],
            "assignments": [
                {
                    "id": a.id,
                    "group_id": a.group_id,
                    "group_name": a.group.name,
                    "created_at": a.created_at,
                    "started": progress.get(a.id, (0, 0))[0],
                    "finished": progress.get(a.id, (0, 0))[1],
                }
                for a in sorted(test.assignments, key=lambda a: a.group.name)
            ],
        }
    )
