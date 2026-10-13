import random
from collections import defaultdict
from itertools import zip_longest

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.errors import Conflict, DomainError, NotFound
from app.services.common import get_many_or_404, get_or_404


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
    rng = rng or random.Random()
    ensure_unique_title(session, data.title)
    if data.discipline_id is not None:
        get_or_404(session, models.Discipline, data.discipline_id)
    competencies = get_many_or_404(session, models.Competency, data.competency_ids)

    selected: list[models.Question] = []
    for competency in competencies:
        stmt = select(models.Question).where(models.Question.competency_id == competency.id)
        if data.discipline_id is not None:
            stmt = stmt.where(models.Question.discipline_id == data.discipline_id)
        pool = list(session.scalars(stmt))
        if len(pool) < data.questions_per_competency:
            raise DomainError(
                f"для {competency.code} в банке {len(pool)} вопр., "
                f"а нужно {data.questions_per_competency}"
            )
        selected.extend(pick_questions(pool, data.questions_per_competency, rng))

    test = models.Test(title=data.title, discipline_id=data.discipline_id)
    test.test_questions = [
        models.TestQuestion(question=q, position=i) for i, q in enumerate(selected)
    ]
    session.add(test)
    session.commit()
    return test


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
    session.add(assignment)
    session.commit()
    return assignment


def _test_questions(session: Session, test_id: int) -> list[models.Question]:
    rows = session.scalars(
        select(models.TestQuestion)
        .where(models.TestQuestion.test_id == test_id)
        .order_by(models.TestQuestion.position)
        .options(selectinload(models.TestQuestion.question).selectinload(models.Question.options))
    )
    return [tq.question for tq in rows]


def start_attempt(
    session: Session, assignment_id: int, student: models.Student
) -> tuple[models.Attempt, list[models.Question]]:
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
        attempt = models.Attempt(assignment_id=assignment.id, student_id=student.id)
        session.add(attempt)
        session.commit()
    return attempt, _test_questions(session, assignment.test_id)


def submit_attempt(
    session: Session, attempt_id: int, student: models.Student, data: schemas.AttemptSubmit
) -> models.Attempt:
    attempt = session.get(models.Attempt, attempt_id)
    if attempt is None or attempt.student_id != student.id:
        raise NotFound(f"попытка {attempt_id} не найдена")
    if attempt.finished_at is not None:
        raise Conflict("попытка уже завершена")

    questions = {q.id: q for q in _test_questions(session, attempt.assignment.test_id)}
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
