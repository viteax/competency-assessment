"""Схемы API: загрузка вопросов из ФОС дисциплины (Word)."""

from typing import Literal

from pydantic import BaseModel

from app.models import Difficulty, QuestionKind


class FundQuestionItem(BaseModel):
    number: int  # по порядку в разделе компетенции
    competency: str | None
    kind: QuestionKind
    difficulty: Difficulty
    text: str
    answer: list[str]  # как будет сохранено: ответы, порядок или пары
    status: Literal["new", "duplicate", "error"]
    error: str | None = None


class FundCompetencyItem(BaseModel):
    code: str
    description: str
    exists: bool


class FundDocumentPreview(BaseModel):
    filename: str
    direction: str  # из шапки документа
    direction_id: int | None  # куда загружается; None – не найдено (см. error)
    discipline: str | None
    discipline_exists: bool
    semester: int | None
    competencies: list[FundCompetencyItem]
    questions: list[FundQuestionItem]
    warnings: list[str]
    error: str | None = None  # документ целиком не загрузится


class FundPreview(BaseModel):
    documents: list[FundDocumentPreview]


class FundResult(BaseModel):
    created_questions: int = 0
    duplicates: int = 0  # уже были в банке – пропущены
    errors: int = 0  # не разобраны – пропущены
    created_disciplines: int = 0
    created_competencies: int = 0
    directions: list[str] = []  # коды направлений, куда добавлены вопросы
