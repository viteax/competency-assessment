"""Схемы API: банк вопросов."""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models import Difficulty, QuestionKind
from app.schemas.base import ORM

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AnswerOptionIn(BaseModel):
    text: Text
    # Задание на соответствие: у элемента левого столбца – номер его пары в списке options
    # (у элементов правого столбца пусто).
    match_index: int | None = None


class AnswerOptionOut(ORM):
    id: int
    text: str
    is_correct: bool
    position: int
    match_id: int | None


class AnswerOptionUpdate(AnswerOptionIn):
    id: int | None = None  # None – новый вариант


class QuestionIn(BaseModel):
    """Вопрос. Что означают options, зависит от типа (kind):

    - open – допустимые ответы (слово или фраза), регистр не важен;
    - sequence – элементы в правильном порядке;
    - matching – левый столбец (у каждого match_index – его пара) и правый столбец
      (match_index пуст; лишние элементы правого столбца допустимы).
    """

    competency_id: int
    indicator_id: int | None = None
    discipline_id: int | None = None
    text: Text
    kind: QuestionKind
    difficulty: Difficulty = Difficulty.BASIC
    options: list[AnswerOptionIn] = Field(min_length=1)

    @model_validator(mode="after")
    def options_fit_kind(self) -> "QuestionIn":
        options = self.options
        if self.kind != QuestionKind.MATCHING and any(o.match_index is not None for o in options):
            raise ValueError("пары задаются только в задании на соответствие")
        if self.kind == QuestionKind.SEQUENCE:
            if len(options) < 2:
                raise ValueError("в последовательности нужно не меньше двух элементов")
        elif self.kind == QuestionKind.MATCHING:
            left = [o for o in options if o.match_index is not None]
            right = {i for i, o in enumerate(options) if o.match_index is None}
            targets = [o.match_index for o in left]
            if len(left) < 2:
                raise ValueError("в задании на соответствие нужно не меньше двух пар")
            if not set(targets) <= right or len(set(targets)) != len(targets):
                raise ValueError(
                    "каждый элемент левого столбца должен ссылаться на свой элемент правого"
                )
        return self


class QuestionUpdate(QuestionIn):
    options: list[AnswerOptionUpdate] = Field(min_length=1)


class QuestionOut(ORM):
    id: int
    competency_id: int
    indicator_id: int | None
    discipline_id: int | None
    text: str
    kind: QuestionKind
    difficulty: Difficulty
    options: list[AnswerOptionOut]
    in_use: bool  # входит в собранные тесты: менять можно только формулировки
