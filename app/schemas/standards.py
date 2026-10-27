"""Схемы API: профстандарт."""

from pydantic import BaseModel, Field

from app.schemas.base import ORM


class LaborFunctionIn(BaseModel):
    code: str = Field(examples=["A/01.3"])
    name: str
    competency_ids: list[int] = []
    # Задано – связи ТФ ⇒ компетенции меняются только у этого направления (competency_ids –
    # его компетенции), связи других направлений остаются. Не задано – заменяются все.
    direction_id: int | None = None


class LaborFunctionCreate(LaborFunctionIn):
    general_function_id: int


class LaborFunctionOut(ORM):
    id: int
    general_function_id: int
    code: str
    name: str
    competency_ids: list[int]


class GeneralLaborFunctionIn(BaseModel):
    code: str = Field(examples=["A"])
    name: str
    qualification_level: int
    functions: list[LaborFunctionIn] = []


class GeneralLaborFunctionUpdate(BaseModel):
    code: str
    name: str
    qualification_level: int


class GeneralLaborFunctionCreate(GeneralLaborFunctionUpdate):
    standard_id: int


class GeneralLaborFunctionOut(ORM):
    id: int
    standard_id: int
    code: str
    name: str
    qualification_level: int
    functions: list[LaborFunctionOut]


class ProfStandardIn(BaseModel):
    code: str = Field(examples=["06.001"])
    name: str = Field(examples=["Программист"])
    general_functions: list[GeneralLaborFunctionIn] = []


class ProfStandardUpdate(BaseModel):
    code: str
    name: str


class ProfStandardOut(ORM):
    id: int
    code: str
    name: str
    general_functions: list[GeneralLaborFunctionOut]
