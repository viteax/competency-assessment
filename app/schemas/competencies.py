"""Схемы API: компетенции."""

from pydantic import BaseModel, Field, model_validator

from app.models import CompetencyKind
from app.schemas.base import ORM


class IndicatorIn(BaseModel):
    code: str = Field(examples=["ОПК-5.1"])
    description: str


class IndicatorOut(ORM, IndicatorIn):
    id: int
    competency_id: int


class IndicatorCreate(IndicatorIn):
    competency_id: int


class CompetencyIn(BaseModel):
    code: str = Field(examples=["ОПК-5"])
    kind: CompetencyKind
    description: str
    indicators: list[IndicatorIn] = []


class CompetencyUpdate(BaseModel):
    code: str
    kind: CompetencyKind
    description: str


class CompetencyOut(ORM):
    id: int
    code: str
    kind: CompetencyKind
    description: str
    indicators: list[IndicatorOut]


class DisciplineIn(BaseModel):
    name: str = Field(examples=["Математика"])
    competency_ids: list[int] = []


class DisciplineOut(ORM):
    id: int
    name: str
    competency_ids: list[int]


class QuotaIn(BaseModel):
    competency_id: int
    questions: int = Field(ge=1, le=200)


class QuotaOut(ORM, QuotaIn):
    pass


class CurriculumEntryIn(BaseModel):
    direction_id: int
    discipline_id: int
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
