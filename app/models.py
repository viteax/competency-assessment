"""Модель предметной области.

Учебная часть:      Direction -> Group -> Student (<- User со ролью student)
Компетенции ФГОС:   Competency (УК/ОПК/ПК) -> Indicator, Discipline <-> Competency
Профстандарт:       ProfStandard -> GeneralLaborFunction (ОТФ) -> LaborFunction (ТФ) <-> Competency
Тестирование:       Question -> AnswerOption, Test -> TestQuestion,
                    Assignment (тест назначен группе) -> Attempt (попытка студента) -> AttemptAnswer
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Role(enum.StrEnum):
    ADMIN = "admin"
    STUDENT = "student"


class CompetencyKind(enum.StrEnum):
    UK = "УК"
    OPK = "ОПК"
    PK = "ПК"


discipline_competency = Table(
    "discipline_competency",
    Base.metadata,
    Column("discipline_id", ForeignKey("discipline.id", ondelete="CASCADE"), primary_key=True),
    Column("competency_id", ForeignKey("competency.id", ondelete="CASCADE"), primary_key=True),
)

labor_function_competency = Table(
    "labor_function_competency",
    Base.metadata,
    Column(
        "labor_function_id", ForeignKey("labor_function.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("competency_id", ForeignKey("competency.id", ondelete="CASCADE"), primary_key=True),
)


# --- Учебная часть ---------------------------------------------------------


class Direction(Base):
    """Направление подготовки, например 09.03.04 «Программная инженерия»."""

    __tablename__ = "direction"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(255))

    groups: Mapped[list["Group"]] = relationship(back_populates="direction")


class Group(Base):
    __tablename__ = "study_group"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    direction_id: Mapped[int] = mapped_column(ForeignKey("direction.id"))

    direction: Mapped[Direction] = relationship(back_populates="groups")
    students: Mapped[list["Student"]] = relationship(back_populates="group")


class Student(Base):
    __tablename__ = "student"
    __table_args__ = (UniqueConstraint("external_id", name="uq_student_external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))
    group_id: Mapped[int] = mapped_column(ForeignKey("study_group.id"))
    email: Mapped[str | None] = mapped_column(String(255))
    # Идентификатор во внешней системе (СДО): индивидуальный номер или логин.
    external_id: Mapped[str | None] = mapped_column(String(64))

    group: Mapped[Group] = relationship(back_populates="students")


class User(Base):
    """Учётная запись. Студенческая учётка привязана к записи Student."""

    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, values_callable=lambda e: [m.value for m in e]))
    student_id: Mapped[int | None] = mapped_column(ForeignKey("student.id"), unique=True)
    # Выданный администратором пароль нужно сменить при первом входе.
    must_change_password: Mapped[bool] = mapped_column(default=False, server_default=false())
    # Увеличивается при смене/сбросе пароля — все ранее выданные токены перестают действовать.
    token_version: Mapped[int] = mapped_column(default=0, server_default="0")

    student: Mapped[Student | None] = relationship()


class LoginFailure(Base):
    """Неудачная попытка входа — для защиты от перебора паролей."""

    __tablename__ = "login_failure"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    ip: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class AuditEntry(Base):
    """Журнал изменяющих действий: кто, когда, что вызвал и с каким результатом."""

    __tablename__ = "audit_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"))
    username: Mapped[str] = mapped_column(String(64))  # на случай, если учётку удалят
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(String(255))
    status_code: Mapped[int] = mapped_column(Integer)
    ip: Mapped[str] = mapped_column(String(64))


# --- Компетенции -----------------------------------------------------------


class Competency(Base):
    __tablename__ = "competency"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)  # "ОПК-5"
    kind: Mapped[CompetencyKind] = mapped_column(
        Enum(CompetencyKind, values_callable=lambda e: [m.value for m in e])
    )
    description: Mapped[str] = mapped_column(Text)

    indicators: Mapped[list["Indicator"]] = relationship(
        back_populates="competency", cascade="all, delete-orphan"
    )
    disciplines: Mapped[list["Discipline"]] = relationship(
        secondary=discipline_competency, back_populates="competencies"
    )
    labor_functions: Mapped[list["LaborFunction"]] = relationship(
        secondary=labor_function_competency, back_populates="competencies"
    )


class Indicator(Base):
    """Индикатор достижения компетенции, например ОПК-5.1."""

    __tablename__ = "indicator"

    id: Mapped[int] = mapped_column(primary_key=True)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competency.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(16), unique=True)
    description: Mapped[str] = mapped_column(Text)

    competency: Mapped[Competency] = relationship(back_populates="indicators")


class Discipline(Base):
    __tablename__ = "discipline"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)

    competencies: Mapped[list[Competency]] = relationship(
        secondary=discipline_competency, back_populates="disciplines"
    )

    @property
    def competency_ids(self) -> list[int]:
        return [c.id for c in self.competencies]


# --- Профстандарт ----------------------------------------------------------


class ProfStandard(Base):
    """Профессиональный стандарт, например 06.001 «Программист»."""

    __tablename__ = "prof_standard"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(255))

    general_functions: Mapped[list["GeneralLaborFunction"]] = relationship(
        back_populates="standard", cascade="all, delete-orphan"
    )


class GeneralLaborFunction(Base):
    """Обобщённая трудовая функция (ОТФ)."""

    __tablename__ = "general_labor_function"
    __table_args__ = (UniqueConstraint("standard_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    standard_id: Mapped[int] = mapped_column(ForeignKey("prof_standard.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(8))  # "A"
    name: Mapped[str] = mapped_column(Text)
    qualification_level: Mapped[int] = mapped_column(Integer)

    standard: Mapped[ProfStandard] = relationship(back_populates="general_functions")
    functions: Mapped[list["LaborFunction"]] = relationship(
        back_populates="general_function", cascade="all, delete-orphan"
    )


class LaborFunction(Base):
    """Трудовая функция (ТФ)."""

    __tablename__ = "labor_function"
    __table_args__ = (UniqueConstraint("general_function_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    general_function_id: Mapped[int] = mapped_column(
        ForeignKey("general_labor_function.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(String(16))  # "A/01.3"
    name: Mapped[str] = mapped_column(Text)

    general_function: Mapped[GeneralLaborFunction] = relationship(back_populates="functions")
    competencies: Mapped[list[Competency]] = relationship(
        secondary=labor_function_competency, back_populates="labor_functions"
    )

    @property
    def competency_ids(self) -> list[int]:
        return [c.id for c in self.competencies]


# --- Банк вопросов ---------------------------------------------------------


class Question(Base):
    __tablename__ = "question"

    id: Mapped[int] = mapped_column(primary_key=True)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competency.id"))
    indicator_id: Mapped[int | None] = mapped_column(ForeignKey("indicator.id"))
    discipline_id: Mapped[int | None] = mapped_column(ForeignKey("discipline.id"))
    text: Mapped[str] = mapped_column(Text)

    competency: Mapped[Competency] = relationship()
    indicator: Mapped[Indicator | None] = relationship()
    discipline: Mapped[Discipline | None] = relationship()
    options: Mapped[list["AnswerOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="AnswerOption.id"
    )
    test_links: Mapped[list["TestQuestion"]] = relationship(viewonly=True)

    @property
    def in_use(self) -> bool:
        return bool(self.test_links)


class AnswerOption(Base):
    __tablename__ = "answer_option"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(default=False)

    question: Mapped[Question] = relationship(back_populates="options")


# --- Тесты и прохождение ---------------------------------------------------


class Test(Base):
    __tablename__ = "test"
    __table_args__ = (UniqueConstraint("title", name="uq_test_title"),)
    __test__ = False  # не путать pytest

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    discipline_id: Mapped[int | None] = mapped_column(ForeignKey("discipline.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    discipline: Mapped[Discipline | None] = relationship()
    test_questions: Mapped[list["TestQuestion"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="TestQuestion.position"
    )

    assignments: Mapped[list["Assignment"]] = relationship(viewonly=True)

    @property
    def question_ids(self) -> list[int]:
        return [tq.question_id for tq in self.test_questions]

    @property
    def group_ids(self) -> list[int]:
        return [a.group_id for a in self.assignments]


class TestQuestion(Base):
    __tablename__ = "test_question"
    __test__ = False

    test_id: Mapped[int] = mapped_column(
        ForeignKey("test.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)

    test: Mapped[Test] = relationship(back_populates="test_questions")
    question: Mapped[Question] = relationship()


class Assignment(Base):
    """Тест, назначенный администратором группе."""

    __tablename__ = "assignment"
    __table_args__ = (UniqueConstraint("test_id", "group_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("test.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("study_group.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    test: Mapped[Test] = relationship()
    group: Mapped[Group] = relationship()


class Attempt(Base):
    __tablename__ = "attempt"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignment.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[int | None] = mapped_column(Integer)
    max_score: Mapped[int | None] = mapped_column(Integer)

    assignment: Mapped[Assignment] = relationship()
    student: Mapped[Student] = relationship()
    answers: Mapped[list["AttemptAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class AttemptAnswer(Base):
    __tablename__ = "attempt_answer"

    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("attempt.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), primary_key=True)
    option_id: Mapped[int | None] = mapped_column(ForeignKey("answer_option.id"))
    is_correct: Mapped[bool] = mapped_column(default=False)

    attempt: Mapped[Attempt] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship()
