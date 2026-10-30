"""Схемы API: загрузка учебного плана из «Планов»."""

from typing import Literal

from pydantic import BaseModel

from app.models import DisciplineKind

Status = Literal["new", "update", "same"]


class PlanDirection(BaseModel):
    code: str
    name: str
    profile: str | None
    year: int | None  # год начала подготовки
    id: int | None  # есть в базе – его id, нет – будет создано


class PlanCandidate(BaseModel):
    """Существующий план с незаполненными полями, который можно дополнить этим файлом."""

    id: int
    label: str


class PlanCompetencyItem(BaseModel):
    code: str
    description: str
    status: Status
    existing_description: str | None


class PlanDisciplineItem(BaseModel):
    code: str  # индекс в плане
    name: str
    kind: DisciplineKind
    first_semester: int | None
    last_semester: int | None
    competency_codes: list[str]
    status: Status
    changes: list[str]  # что поменяется у существующей


class PlanFunctionItem(BaseModel):
    code: str
    name: str
    competency_codes: list[str]
    status: Status  # update – добавятся связи с компетенциями


class PlanGeneralItem(BaseModel):
    code: str
    name: str
    level: int
    exists: bool
    functions: list[PlanFunctionItem]


class PlanStandardItem(BaseModel):
    code: str
    name: str
    exists: bool
    general_functions: list[PlanGeneralItem]


class PlanPreview(BaseModel):
    filename: str
    direction: PlanDirection
    candidates: list[PlanCandidate]
    competencies: list[PlanCompetencyItem]
    disciplines: list[PlanDisciplineItem]
    standards: list[PlanStandardItem]
    skipped: list[str]  # есть в плане, но не загружается (ГИА)
    warnings: list[str]


class PlanResult(BaseModel):
    direction_id: int
    created_direction: bool = False
    created_competencies: int = 0
    updated_competencies: int = 0
    created_disciplines: int = 0
    updated_disciplines: int = 0
    created_standards: int = 0
    created_general_functions: int = 0
    created_labor_functions: int = 0
    linked_labor_functions: int = 0  # новые связи ТФ ⇒ компетенции
