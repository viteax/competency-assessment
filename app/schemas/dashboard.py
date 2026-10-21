"""Схемы API: главная страница администратора."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Куда ведёт ссылка из «Требует внимания»: раздел интерфейса и вкладка в нём.
Target = Literal["curriculum", "groups", "students", "bank", "labor_functions", "tests"]


class DashboardCounts(BaseModel):
    groups: int
    students: int
    students_with_account: int  # зарегистрировались сами или получили логин
    teachers: int
    questions: int
    tests: int


class TeacherProgress(BaseModel):
    teacher: str
    discipline: str
    discipline_id: int
    required: int
    done: int  # не больше квоты по каждой компетенции


class AssignmentProgress(BaseModel):
    test_id: int
    test: str
    group_id: int
    group: str
    assigned_at: datetime
    students: int
    finished: int


class AttentionItem(BaseModel):
    text: str
    target: Target


class Dashboard(BaseModel):
    counts: DashboardCounts
    teachers: list[TeacherProgress]
    assignments: list[AssignmentProgress]  # последние назначенные тесты
    attention: list[AttentionItem]
