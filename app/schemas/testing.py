"""Схемы API: тесты."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import QuestionKind
from app.schemas.base import ORM
from app.schemas.questions import QuestionOut


class TestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # опечатка в поле не должна молча игнорироваться

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    competency_ids: list[int] = Field(min_length=1)
    # Вопросы берутся только из этих дисциплин; пусто – из любых.
    discipline_ids: list[int] = []
    questions_per_competency: int = Field(default=5, ge=1, le=50)
    semester: int | None = Field(default=None, ge=1, le=12)
    # Сколько вариантов собрать (обычно – по числу студентов группы). Не задано – столько
    # непересекающихся вариантов, на сколько хватает вопросов.
    variant_count: int | None = Field(default=None, ge=1, le=300)


class TestOut(ORM):
    id: int
    title: str
    semester: int | None
    discipline_ids: list[int]
    created_at: datetime
    question_ids: list[int]
    variant_count: int
    questions_per_variant: int
    group_ids: list[int]  # каким группам уже назначен


class TestVariantOut(BaseModel):
    variant: int
    questions: list[QuestionOut]


class TestAssignmentOut(BaseModel):
    id: int
    group_id: int
    group_name: str
    created_at: datetime
    started: int  # студентов открыли тест
    finished: int  # и сдали


class TestDetail(TestOut):
    variants: list[TestVariantOut]
    assignments: list[TestAssignmentOut]


class PlanDiscipline(BaseModel):
    id: int
    name: str
    first_semester: int
    last_semester: int
    competency_ids: list[int]


class QuestionCount(BaseModel):
    competency_id: int
    discipline_id: int
    count: int


class AssemblyPlan(BaseModel):
    """Что доступно для оценки остаточных знаний группы в семестре."""

    group_id: int
    semester: int
    finished: list[PlanDiscipline]  # завершены до этого семестра – из них берутся вопросы
    not_finished: list[PlanDiscipline]  # ещё изучаются или впереди
    unplanned: list[str]  # дисциплины, у которых семестры не указаны ни в одном учебном плане
    question_counts: list[QuestionCount]  # вопросов в банке по завершённым дисциплинам


class AssignmentIn(BaseModel):
    test_id: int
    group_id: int


class AssignmentOut(ORM, AssignmentIn):
    id: int
    created_at: datetime


class AttemptSummary(ORM):
    id: int
    finished_at: datetime | None
    score: int | None
    max_score: int | None


class StudentAssignmentOut(BaseModel):
    id: int
    title: str
    question_count: int
    created_at: datetime
    attempt: AttemptSummary | None


# Вопрос в том виде, в каком его видит студент: без признака правильности.
class StudentOptionOut(ORM):
    id: int
    text: str


class StudentQuestionOut(BaseModel):
    """Без правильных ответов: в открытом задании варианты не передаются вовсе."""

    id: int
    text: str
    kind: QuestionKind
    options: list[StudentOptionOut]  # варианты / элементы / левый столбец
    right: list[StudentOptionOut] = []  # правый столбец задания на соответствие


class AttemptStart(BaseModel):
    assignment_id: int


class AttemptStarted(BaseModel):
    attempt_id: int
    title: str
    questions: list[StudentQuestionOut]


class AnswerIn(BaseModel):
    """Ответ на вопрос; заполняется поле, соответствующее типу задания."""

    question_id: int
    text: str | None = Field(default=None, max_length=500)  # open
    order: list[int] | None = None  # sequence: id элементов по порядку
    pairs: dict[int, int] | None = None  # matching: id левого → id правого


class AttemptSubmit(BaseModel):
    answers: list[AnswerIn]
