"""Схемы API: пользователи."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models import Role
from app.schemas.base import ORM


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    role: Role
    student_id: int | None = None
    full_name: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def student_link(self) -> "UserCreate":
        if (self.role == Role.STUDENT) != (self.student_id is not None):
            raise ValueError("student_id указывается только и обязательно для роли student")
        if self.role == Role.TEACHER and not (self.full_name or "").strip():
            raise ValueError("у преподавателя должно быть ФИО")
        return self


class UserOut(ORM):
    id: int
    username: str
    full_name: str | None
    role: Role
    student_id: int | None
    must_change_password: bool
    created_at: datetime


class RegistrationGroup(ORM):
    id: int
    name: str


class StudentRegistration(BaseModel):
    group_id: int
    full_name: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class Registered(BaseModel):
    username: str  # логин для входа (ФИО, у полных тёзок – ФИО и группа)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class PasswordReset(BaseModel):
    username: str
    password: str  # показывается один раз
