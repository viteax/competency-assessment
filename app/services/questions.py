from sqlalchemy.orm import Session

from app import models, schemas
from app.errors import Conflict, DomainError
from app.services.common import get_or_404, save


def _check_links(session: Session, data: schemas.QuestionIn) -> None:
    get_or_404(session, models.Competency, data.competency_id)
    if data.indicator_id is not None:
        indicator = get_or_404(session, models.Indicator, data.indicator_id)
        if indicator.competency_id != data.competency_id:
            raise DomainError("индикатор относится к другой компетенции")
    if data.discipline_id is not None:
        get_or_404(session, models.Discipline, data.discipline_id)


def _build_options(data: schemas.QuestionIn) -> list[models.AnswerOption]:
    """Варианты в порядке списка (для последовательности это правильный порядок)."""
    open_kind = data.kind == models.QuestionKind.OPEN
    options = [
        models.AnswerOption(text=o.text, is_correct=open_kind, position=i)
        for i, o in enumerate(data.options)
    ]
    for option, o in zip(options, data.options, strict=True):
        if o.match_index is not None:
            option.match = options[o.match_index]
    return options


def create_question(session: Session, data: schemas.QuestionIn) -> models.Question:
    _check_links(session, data)
    question = models.Question(
        competency_id=data.competency_id,
        indicator_id=data.indicator_id,
        discipline_id=data.discipline_id,
        text=data.text,
        kind=data.kind,
        difficulty=data.difficulty,
        options=_build_options(data),
    )
    return save(session, question)


def _same_answers(question: models.Question, data: schemas.QuestionUpdate) -> bool:
    """Те же варианты с тем же правильным ответом, порядком и парами (тексты – любые)."""
    current = {o.id: o for o in question.options}
    new_ids = [o.id for o in data.options]
    old_ids = [o.id for o in question.options]
    if data.kind != question.kind or sorted(new_ids, key=str) != sorted(old_ids, key=str):
        return False
    # Порядок важен только в последовательности; в остальных типах – это порядок показа.
    if data.kind == models.QuestionKind.SEQUENCE and new_ids != old_ids:
        return False
    for o in data.options:
        option = current[o.id]
        match_id = data.options[o.match_index].id if o.match_index is not None else None
        if option.match_id != match_id:
            return False
    return True


def update_question(
    session: Session, question: models.Question, data: schemas.QuestionUpdate
) -> models.Question:
    """Обновляет вопрос.

    Если вопрос уже попал в собранные тесты, по нему могут быть ответы студентов. Тогда
    разрешено менять только формулировки, индикатор и дисциплину: состав вариантов,
    правильный ответ и компетенция влияют на уже посчитанные результаты.
    """
    _check_links(session, data)
    if question.in_use:
        if not _same_answers(question, data) or data.competency_id != question.competency_id:
            raise Conflict(
                "вопрос уже используется в тестах: можно менять только формулировки, "
                "индикатор, дисциплину и сложность. Для других изменений создайте новый вопрос"
            )
        current = {o.id: o for o in question.options}
        for o in data.options:
            current[o.id].text = o.text
    else:
        question.options = []
        session.flush()  # старые варианты удаляются до вставки новых (ссылки match)
        question.kind = data.kind
        question.options = _build_options(data)
    question.competency_id = data.competency_id
    question.indicator_id = data.indicator_id
    question.discipline_id = data.discipline_id
    question.difficulty = data.difficulty
    question.text = data.text
    session.commit()
    return question


def delete_question(session: Session, question: models.Question) -> None:
    if question.in_use:
        raise Conflict("вопрос используется в тестах, удалить его нельзя")
    session.delete(question)
    session.commit()
