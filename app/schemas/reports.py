"""Схемы API: отчёты."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.models import CompetencyKind

# Уровень развития компетенции для вывода студенту: до 40% верных – «требует внимания»,
# 40–79% – «в процессе формирования», от 80% – «хорошо развита».
CompetencyLevel = Literal["attention", "forming", "good"]


class CompetencyResult(BaseModel):
    competency_id: int
    code: str
    name: str
    kind: CompetencyKind
    correct: int
    total: int
    ratio: float
    mastered: bool
    level: CompetencyLevel


class AttemptResult(BaseModel):
    attempt_id: int
    score: int
    max_score: int
    finished_at: datetime
    competencies: list[CompetencyResult] = []  # разбор этой попытки по компетенциям


class LaborFunctionResult(BaseModel):
    labor_function_id: int
    code: str
    name: str
    competency_codes: list[str]
    covered: bool


class GeneralLaborFunctionResult(BaseModel):
    standard_code: str
    code: str
    name: str
    functions: list[LaborFunctionResult]
    covered: bool


class StudentCompetencyReport(BaseModel):
    student_id: int
    full_name: str
    competencies: list[CompetencyResult]
    tested_at: datetime | None = None  # последняя сданная попытка (в отчёте по группе)


class GroupCompetencyReport(BaseModel):
    group_id: int
    name: str
    students: list[StudentCompetencyReport]


class ProfileAxis(BaseModel):
    """Ось «розы ветров»: компетенция или трудовая функция."""

    code: str
    name: str
    value: float | None  # уровень 0..1; None – не проверялась
    measured: int  # компетенция: сколько студентов проверено; ТФ: сколько её компетенций
    total: int  # компетенция: студентов в выборке; ТФ: всего её компетенций


class Profile(BaseModel):
    students: int  # у скольких студентов есть результаты
    legend: list[str] = []  # подпись к диаграмме: группа, курс, направление, кто прошёл
    competencies: list[ProfileAxis]
    labor_functions: list[ProfileAxis]


class ChartExport(BaseModel):
    """«Роза ветров» для выгрузки в Word: картинка PNG (base64) с подписью и таблицей осей."""

    title: str = Field(min_length=1, max_length=200)
    legend: list[Annotated[str, Field(max_length=300)]] = Field(default=[], max_length=10)
    rows: list[Annotated[list[Annotated[str, Field(max_length=500)]], Field(max_length=3)]] = Field(
        default=[], max_length=100
    )
    image: str = Field(max_length=4_000_000)
