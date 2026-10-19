"""Схемы API: импорт студентов."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.base import ORM


class StudentImportRowIn(BaseModel):
    full_name: str = Field(min_length=1)
    email: str | None = None
    external_id: str | None = Field(default=None, max_length=64)
    login: str | None = None
    group: str | None = None
    program: str | None = None  # образовательная программа – направление для новой группы


class StudentImportRow(StudentImportRowIn):
    full_name: str  # в предпросмотре может быть пустым – тогда это проблема строки
    row: int
    role: str | None
    is_student: bool  # роль в СДО похожа на студенческую (или колонки ролей нет)
    status: Literal["new", "update", "same"]
    existing_student_id: int | None
    existing_group: str | None
    problems: list[str]


class StudentImportPreview(BaseModel):
    filename: str
    headers: list[str]
    mapping: dict[str, int | None]
    rows: list[StudentImportRow]
    missing_groups: list[str]


class StudentImportApply(BaseModel):
    students: list[StudentImportRowIn] = Field(min_length=1)
    default_group_id: int | None = None  # для строк без группы
    direction_id: int | None = None  # для групп, которых ещё нет
    create_accounts: bool = True


class CreatedAccount(BaseModel):
    full_name: str
    group: str
    username: str
    password: str


class StudentImportResult(BaseModel):
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    created_groups: list[str] = []
    accounts: list[CreatedAccount] = []


class AuditEntryOut(ORM):
    id: int
    created_at: datetime
    username: str
    method: str
    path: str
    status_code: int
    ip: str


class SystemSettings(BaseModel):
    # Доля верных ответов, начиная с которой компетенция считается сформированной.
    mastery_threshold: float = Field(gt=0, le=1)
