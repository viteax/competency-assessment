import json
import random
from collections import Counter, defaultdict
from math import comb, prod

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.errors import Conflict, DomainError, NotFound
from app.services.common import get_many_or_404, get_or_404, save


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
            f"тест «{title}» уже есть – выберите другое название или назначьте существующий тест"
        )


def _variant_chunks(
    pool: list[models.Question], k: int, count: int, rng: random.Random
) -> list[list[models.Question]]:
    """`count` наборов по k разных вопросов из пула, вопросы расходуются равномерно.

    Пул идёт по кругу в случайном порядке, каждый новый круг перемешивается заново. Пока
    вопросов хватает, наборы не пересекаются (20 вопросов по 5 – 4 непересекающихся набора);
    дальше вопросы повторяются в разных наборах, но каждый используется примерно одинаково часто.
    """
    stream: list[models.Question] = []
    chunks = []
    for _ in range(count):
        chunk: list[models.Question] = []
        postponed: list[models.Question] = []
        while len(chunk) < k:
            if not stream:
                stream = pool[:]
                rng.shuffle(stream)
            question = stream.pop()
            (postponed if question in chunk else chunk).append(question)
        stream.extend(postponed)  # повторы откладываем на следующие наборы
        chunks.append(chunk)
    return chunks


def create_test(
    session: Session, data: schemas.TestCreate, rng: random.Random | None = None
) -> models.Test:
    """Собирает тест в нескольких вариантах.

    По каждой компетенции нужно k = questions_per_competency вопросов на вариант. Вариантов –
    сколько попросили (обычно по числу студентов группы, чтобы у каждого был свой); пока
    вопросов хватает, варианты не пересекаются, дальше частично пересекаются (3 вопроса из
    одного набора, 2 из другого). Одинаковых вариантов не бывает: если различных сочетаний
    вопросов меньше, чем попросили, вариантов будет столько, сколько сочетаний возможно.
    Без variant_count – столько непересекающихся вариантов, на сколько хватает вопросов.
    """
    rng = rng or random.Random()
    ensure_unique_title(session, data.title)
    disciplines = get_many_or_404(session, models.Discipline, data.discipline_ids)
    competencies = get_many_or_404(session, models.Competency, data.competency_ids)
    if len({c.direction_id for c in competencies} | {d.direction_id for d in disciplines}) > 1:
        raise DomainError(
            "тест собирается по одному направлению: выбраны компетенции или "
            "дисциплины разных направлений"
        )
    k = data.questions_per_competency

    pools: list[list[models.Question]] = []
    for competency in competencies:
        stmt = select(models.Question).where(models.Question.competency_id == competency.id)
        if disciplines:
            stmt = stmt.where(models.Question.discipline_id.in_([d.id for d in disciplines]))
        pools.append(list(session.scalars(stmt.order_by(models.Question.id))))
    short = [
        f"{c.code} – {len(pool)} из {k}"
        for c, pool in zip(competencies, pools, strict=True)
        if len(pool) < k
    ]
    if short:
        where = " в выбранных дисциплинах" if disciplines else ""
        raise DomainError(f"не хватает вопросов{where}: {', '.join(short)}")

    possible = prod(comb(len(pool), k) for pool in pools)  # различных вариантов всего
    wanted = data.variant_count or min(len(pool) // k for pool in pools)
    count = min(wanted, possible)
    per_competency = [_variant_chunks(pool, k, count, rng) for pool in pools]

    variants: list[list[models.Question]] = []
    seen: set[frozenset[int]] = set()
    for chunks in zip(*per_competency, strict=True):
        questions = [q for chunk in chunks for q in chunk]
        key = frozenset(q.id for q in questions)
        attempts = 0
        while key in seen and attempts < 50:  # такой вариант уже есть – собираем заново
            questions = [q for pool in pools for q in rng.sample(pool, k)]
            key = frozenset(q.id for q in questions)
            attempts += 1
        if key not in seen:
            seen.add(key)
            variants.append(questions)

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
        raise Conflict("тест уже проходили – удалить его нельзя, иначе пропадут результаты")
    for assignment in test.assignments:
        session.delete(assignment)
    session.delete(test)
    session.commit()


def delete_assignment(session: Session, assignment_id: int) -> None:
    assignment = get_or_404(session, models.Assignment, assignment_id)
    if session.scalar(
        select(models.Attempt.id).where(models.Attempt.assignment_id == assignment.id).limit(1)
    ):
        raise Conflict("группа уже проходит этот тест – снять назначение нельзя")
    session.delete(assignment)
    session.commit()


def assign_test(session: Session, data: schemas.AssignmentIn) -> models.Assignment:
    get_or_404(session, models.Test, data.test_id)
    group = get_or_404(session, models.Group, data.group_id)
    directions = set(
        session.scalars(
            select(models.Competency.direction_id)
            .join(models.Question)
            .join(models.TestQuestion)
            .where(models.TestQuestion.test_id == data.test_id)
            .distinct()
        )
    )
    if directions and group.direction_id not in directions:
        raise DomainError(
            f"тест собран по компетенциям другого направления, чем у группы {group.name}"
        )
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


def shuffle_away(items: list, rng: random.Random) -> None:
    """Перемешивает так, чтобы порядок отличался от исходного: в последовательности
    исходный порядок – правильный ответ."""
    original = items[:]
    rng.shuffle(items)
    if len(items) > 1 and items == original:
        items.append(items.pop(0))


def _for_student(question: models.Question, rng: random.Random) -> schemas.StudentQuestionOut:
    """Вопрос без правильных ответов, варианты перемешаны."""
    kind = question.kind
    as_out = schemas.StudentOptionOut.model_validate
    if kind == models.QuestionKind.OPEN:
        options, right = [], []  # допустимые ответы студенту не передаются
    elif kind == models.QuestionKind.MATCHING:
        options = [as_out(o) for o in question.options if o.match_id is not None]
        right = [as_out(o) for o in question.options if o.match_id is None]
    else:
        options, right = [as_out(o) for o in question.options], []
    if kind == models.QuestionKind.SEQUENCE:
        shuffle_away(options, rng)
    else:
        rng.shuffle(options)
    rng.shuffle(right)
    return schemas.StudentQuestionOut(
        id=question.id, text=question.text, kind=kind, options=options, right=right
    )


def _shuffled_for(attempt: models.Attempt, questions: list[models.Question]):
    """Порядок вопросов и вариантов ответа у каждого студента свой, но при повторном
    открытии теста тот же (зависит от номера попытки)."""
    rng = random.Random(attempt.id)
    result = [_for_student(q, rng) for q in questions]
    rng.shuffle(result)
    return result


def normalize_answer(text: str) -> str:
    """Открытый ответ сравнивается без учёта регистра, «ё/е», лишних пробелов, кавычек и
    точки в конце."""
    text = text.casefold().replace("ё", "е")
    text = text.strip(" \t«»\"'.,;:!?")
    return " ".join(text.split())


def _grade(question: models.Question, answer: schemas.AnswerIn | None) -> tuple[bool, str | None]:
    """(верно ли, ответ для сохранения в JSON). Нет ответа – неверно."""
    if answer is None:
        return False, None
    kind = question.kind
    ids = {o.id for o in question.options}
    if kind == models.QuestionKind.OPEN:
        given = normalize_answer(answer.text or "")
        accepted = {normalize_answer(o.text) for o in question.options}
        return bool(given) and given in accepted, json.dumps({"text": answer.text or ""})
    if kind == models.QuestionKind.SEQUENCE:
        order = answer.order or []
        if not set(order) <= ids:
            raise DomainError(f"в ответе на вопрос {question.id} чужие элементы")
        return order == [o.id for o in question.options], json.dumps({"order": order})
    pairs = answer.pairs or {}  # matching
    if not set(pairs) | set(pairs.values()) <= ids:
        raise DomainError(f"в ответе на вопрос {question.id} чужие элементы")
    correct = {o.id: o.match_id for o in question.options if o.match_id is not None}
    return pairs == correct, json.dumps({"pairs": {str(k): v for k, v in pairs.items()}})


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


def _open_attempt(session: Session, attempt_id: int, student: models.Student) -> models.Attempt:
    """Своя незавершённая попытка; чужие не отличаем от несуществующих."""
    attempt = session.get(models.Attempt, attempt_id)
    if attempt is None or attempt.student_id != student.id:
        raise NotFound(f"попытка {attempt_id} не найдена")
    if attempt.finished_at is not None:
        raise Conflict("попытка уже завершена")
    return attempt


def _answers_by_question(
    questions: dict[int, models.Question], answers: list[schemas.AnswerIn]
) -> dict[int, schemas.AnswerIn]:
    given: dict[int, schemas.AnswerIn] = {}
    for answer in answers:
        if answer.question_id not in questions:
            raise NotFound(f"вопроса {answer.question_id} нет в этом тесте")
        if answer.question_id in given:
            raise DomainError(f"на вопрос {answer.question_id} дано несколько ответов")
        given[answer.question_id] = answer
    return given


def _attempt_questions(session: Session, attempt: models.Attempt) -> dict[int, models.Question]:
    return {q.id: q for q in _test_questions(session, attempt.assignment.test_id, attempt.variant)}


def save_draft(
    session: Session, attempt_id: int, student: models.Student, data: schemas.AttemptSubmit
) -> None:
    """Ответы по ходу теста, в том числе неполные: после обновления страницы или входа с
    другого компьютера студент продолжит с того же места. Ничего не оценивается."""
    attempt = _open_attempt(session, attempt_id, student)
    questions = _attempt_questions(session, attempt)
    given = _answers_by_question(questions, data.answers)
    for question_id, answer in given.items():
        question = questions[question_id]
        if len(answer.order or []) > len(question.options):
            raise DomainError(f"в ответе на вопрос {question_id} лишние элементы")
        _grade(question, answer)  # проверяет, что элементы из этого вопроса
    attempt.draft = json.dumps([a.model_dump(exclude_none=True) for a in given.values()])
    session.commit()


def draft_answers(attempt: models.Attempt) -> list[schemas.AnswerIn]:
    return [schemas.AnswerIn.model_validate(a) for a in json.loads(attempt.draft or "[]")]


def submit_attempt(
    session: Session, attempt_id: int, student: models.Student, data: schemas.AttemptSubmit
) -> models.Attempt:
    attempt = _open_attempt(session, attempt_id, student)
    questions = _attempt_questions(session, attempt)
    given = _answers_by_question(questions, data.answers)

    # Вопросы без ответа засчитываются как неверные. Задание засчитывается целиком:
    # «полное совпадение с верным ответом – 1 балл, иначе 0».
    attempt.answers = []
    score = 0
    for question in questions.values():
        answer = given.get(question.id)
        correct, response = _grade(question, answer)
        score += correct
        attempt.answers.append(
            models.AttemptAnswer(
                question_id=question.id,
                response=response,
                is_correct=correct,
            )
        )
    attempt.score = score
    attempt.max_score = len(questions)
    attempt.finished_at = models.utcnow()
    attempt.draft = None
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


def student_assignments(
    session: Session, student: models.Student
) -> list[schemas.StudentAssignmentOut]:
    """Назначенные группе студента тесты и состояние его попытки по каждому."""
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
