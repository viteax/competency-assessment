"""Схемы API: импорт компетенций."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models import CompetencyKind
from app.schemas.competencies import DisciplineOut

COMPETENCY_CODE = r"^(УК|ОПК|ПК)-\d+$"


class ImportIndicator(BaseModel):
    code: str
    description: str
    exists: bool = False
    changed: bool = False  # есть в БД, но формулировка в файле другая


class ImportCompetency(BaseModel):
    code: str
    kind: CompetencyKind
    description: str
    existing_description: str | None
    status: Literal["new", "update", "same"]
    indicators: list[ImportIndicator]


class ImportPreview(BaseModel):
    filename: str
    discipline_name: str | None
    discipline_exists: bool
    competencies: list[ImportCompetency]
    warnings: list[str]


class ImportIndicatorIn(BaseModel):
    code: str
    description: str = ""


class ImportCompetencyIn(BaseModel):
    code: str = Field(pattern=COMPETENCY_CODE)
    description: str = ""
    indicators: list[ImportIndicatorIn] = []

    @model_validator(mode="after")
    def indicators_belong(self) -> "ImportCompetencyIn":
        for ind in self.indicators:
            prefix, _, num = ind.code.rpartition(".")
            if prefix != self.code or not num.isdigit():
                raise ValueError(f"индикатор {ind.code} не относится к {self.code}")
        return self


class ImportApply(BaseModel):
    discipline_name: str | None = None
    overwrite_descriptions: bool = False
    competencies: list[ImportCompetencyIn] = Field(min_length=1)


class ImportResult(BaseModel):
    created_competencies: int = 0
    updated_competencies: int = 0
    created_indicators: int = 0
    updated_indicators: int = 0
    created_discipline: bool = False
    linked_competencies: int = 0
    discipline: DisciplineOut | None = None
