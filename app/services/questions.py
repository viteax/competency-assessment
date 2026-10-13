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


def create_question(session: Session, data: schemas.QuestionIn) -> models.Question:
    _check_links(session, data)
    question = models.Question(
        competency_id=data.competency_id,
        indicator_id=data.indicator_id,
        discipline_id=data.discipline_id,
        text=data.text,
        options=[models.AnswerOption(text=o.text, is_correct=o.is_correct) for o in data.options],
    )
    return save(session, question)


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
        current = {o.id: o for o in question.options}
        same_options = {o.id for o in data.options} == set(current) and all(
            current[o.id].is_correct == o.is_correct for o in data.options
        )
        if not same_options or data.competency_id != question.competency_id:
            raise Conflict(
                "вопрос уже используется в тестах: можно менять только формулировки, "
                "индикатор и дисциплину. Для других изменений создайте новый вопрос"
            )
        for o in data.options:
            current[o.id].text = o.text
    else:
        question.options = [
            models.AnswerOption(text=o.text, is_correct=o.is_correct) for o in data.options
        ]
    question.competency_id = data.competency_id
    question.indicator_id = data.indicator_id
    question.discipline_id = data.discipline_id
    question.text = data.text
    session.commit()
    return question


def delete_question(session: Session, question: models.Question) -> None:
    if question.in_use:
        raise Conflict("вопрос используется в тестах, удалить его нельзя")
    session.delete(question)
    session.commit()
