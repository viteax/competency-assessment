"""Схемы API: учебная часть."""

from pydantic import BaseModel, Field

from app.schemas.base import ORM


class DirectionIn(BaseModel):
    code: str = Field(examples=["09.03.04"])
    name: str = Field(examples=["Программная инженерия"])


class DirectionOut(ORM, DirectionIn):
    id: int


class GroupIn(BaseModel):
    name: str = Field(examples=["ПИ-21"])
    direction_id: int
    start_year: int | None = Field(default=None, ge=2000, le=2100, examples=[2024])


class GroupOut(ORM, GroupIn):
    id: int
    current_semester: int | None  # по году набора и сегодняшней дате


class StudentIn(BaseModel):
    full_name: str
    group_id: int
    email: str | None = None
    external_id: str | None = None


class StudentOut(ORM, StudentIn):
    id: int
