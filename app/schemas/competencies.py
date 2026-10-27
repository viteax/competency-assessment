"""Схемы API: компетенции, дисциплины, учебный план."""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models import CompetencyKind, DisciplineKind
from app.schemas.base import ORM

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class IndicatorIn(BaseModel):
    code: str = Field(examples=["ОПК-5.1"])
    description: str


class IndicatorOut(ORM, IndicatorIn):
    id: int
    competency_id: int


class IndicatorCreate(IndicatorIn):
    competency_id: int


class CompetencyUpdate(BaseModel):
    code: str = Field(examples=["ОПК-5"])
    kind: CompetencyKind
    description: str


class CompetencyIn(CompetencyUpdate):
    direction_id: int  # у каждого направления свои компетенции
    indicators: list[IndicatorIn] = []


class CompetencyOut(ORM):
    id: int
    direction_id: int
    code: str
    kind: CompetencyKind
    description: str
    indicators: list[IndicatorOut]


class DisciplineIn(BaseModel):
    name: Name = Field(examples=["Математика"])
    # Индекс в учебном плане, например Б1.О.02.01; пустой – нет индекса.
    code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)] | None = None
    kind: DisciplineKind = DisciplineKind.REGULAR
    competency_ids: list[int] = []  # только компетенции направления дисциплины


class DisciplineCreate(DisciplineIn):
    direction_id: int


class DisciplineOut(ORM):
    id: int
    direction_id: int
    name: str
    code: str | None
    kind: DisciplineKind
    competency_ids: list[int]


class QuotaIn(BaseModel):
    competency_id: int
    questions: int = Field(ge=1, le=200)


class QuotaOut(ORM, QuotaIn):
    pass


class CurriculumEntryIn(BaseModel):
    discipline_id: int  # направление строки плана – направление дисциплины
    first_semester: int = Field(ge=1, le=12)
    last_semester: int = Field(ge=1, le=12)
    teacher_id: int | None = None  # кто разрабатывает вопросы по дисциплине
    quotas: list[QuotaIn] = []  # сколько вопросов на каждую компетенцию дисциплины

    @model_validator(mode="after")
    def ordered(self) -> "CurriculumEntryIn":
        if self.first_semester > self.last_semester:
            raise ValueError("первый семестр не может быть позже последнего")
        return self


class CurriculumEntryOut(ORM, CurriculumEntryIn):
    id: int
    direction_id: int
    quotas: list[QuotaOut]


class QuotaProgress(BaseModel):
    competency_id: int
    code: str
    description: str
    required: int  # сколько вопросов нужно (0 – квота не задана)
    done: int  # сколько уже в банке


class TeacherDiscipline(BaseModel):
    """Дисциплина в кабинете преподавателя: что и сколько разработать."""

    entry_id: int
    discipline_id: int
    discipline: str
    direction: str
    first_semester: int
    last_semester: int
    competencies: list[QuotaProgress]
    required: int
    done: int  # засчитываются не больше квоты по каждой компетенции
