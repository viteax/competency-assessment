"""Модель предметной области.

Учебная часть:      Direction -> Group -> Student (<- User со ролью student)
Компетенции ФГОС:   Direction -> Competency (УК/ОПК/ПК) -> Indicator,
                    Direction -> Discipline <-> Competency (того же направления)
Профстандарт:       ProfStandard -> GeneralLaborFunction (ОТФ) -> LaborFunction (ТФ) <-> Competency

Компетенции и дисциплины принадлежат направлению: в разных ОП коды компетенций одни и те же
(ОПК-1, ПК-5), а формулировки бывают разные. Профстандарты общие, а связь ТФ с компетенциями
у каждого направления своя – через его компетенции.
Тестирование:       Question -> AnswerOption, Test -> TestQuestion,
                    Assignment (тест назначен группе) -> Attempt (попытка студента) -> AttemptAnswer
"""

import enum
import re
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db import Base
from app.semesters import current_semester


def utcnow() -> datetime:
    return datetime.now(UTC)


class Role(enum.StrEnum):
    ADMIN = "admin"
    TEACHER = "teacher"  # ППС или сотрудник кафедры: составляет вопросы по своим дисциплинам
    STUDENT = "student"


class QuestionKind(enum.StrEnum):
    """Тип задания (названия – как в фонде оценочных материалов)."""

    MATCHING = "matching"  # на установление соответствия
    SEQUENCE = "sequence"  # на установление последовательности
    OPEN = "open"  # открытого типа: ответ словом


class Difficulty(enum.StrEnum):
    BASIC = "basic"  # базовый, 1–3 минуты
    ADVANCED = "advanced"  # повышенный, 3–5 минут


class CompetencyKind(enum.StrEnum):
    UK = "УК"
    OPK = "ОПК"
    PK = "ПК"


class DisciplineKind(enum.StrEnum):
    """Статус дисциплины в учебном плане."""

    REGULAR = "regular"  # обязательная
    ELECTIVE = "elective"  # по выбору (ДВ): студент изучает одну из нескольких
    OPTIONAL = "optional"  # факультатив (ФТД)
    PRACTICE = "practice"  # практика (Б2)


discipline_competency = Table(
    "discipline_competency",
    Base.metadata,
    Column("discipline_id", ForeignKey("discipline.id", ondelete="CASCADE"), primary_key=True),
    Column("competency_id", ForeignKey("competency.id", ondelete="CASCADE"), primary_key=True),
)

# Дисциплины, из вопросов которых собран тест (пусто – из любых).
test_discipline = Table(
    "test_discipline",
    Base.metadata,
    Column("test_id", ForeignKey("test.id", ondelete="CASCADE"), primary_key=True),
    Column("discipline_id", ForeignKey("discipline.id"), primary_key=True),
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


def profile_key(profile: str | None) -> str:
    """Программа для сравнения: без регистра, кавычек, лишних пробелов и разницы «ё/е»."""
    cleaned = re.sub(r"[\"'«»„“”]", "", (profile or "").casefold().replace("ё", "е"))
    return " ".join(cleaned.split())


class Direction(Base):
    """Учебный план: код направления, например 09.03.04 «Программная инженерия», программа
    и год плана. У одного кода планов может быть несколько; группа любого года набора
    учится по одному из них."""

    __tablename__ = "direction"
    # coalesce: в уникальном индексе NULL иначе считались бы разными значениями.
    __table_args__ = (
        Index(
            "uq_direction_plan", "code", "profile_key", text("coalesce(plan_year, 0)"), unique=True
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(255))
    profile: Mapped[str | None] = mapped_column(String(255))
    plan_year: Mapped[int | None] = mapped_column(Integer)
    profile_key: Mapped[str] = mapped_column(String(255), default="", server_default="")

    groups: Mapped[list["Group"]] = relationship(back_populates="direction")

    @validates("profile")
    def _set_profile_key(self, _: str, value: str | None) -> str | None:
        self.profile_key = profile_key(value)
        return value

    @property
    def label(self) -> str:
        """Подпись плана: «15.04.06 Мехатроника, Управление разработками, 2023»."""
        extra = [self.profile, str(self.plan_year) if self.plan_year else None]
        return ", ".join([f"{self.code} {self.name}", *filter(None, extra)])

    @property
    def intake_years(self) -> list[int]:
        return sorted({g.start_year for g in self.groups if g.start_year})


class Group(Base):
    __tablename__ = "study_group"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    direction_id: Mapped[int] = mapped_column(ForeignKey("direction.id"))
    # Год набора: по нему считается текущий семестр группы.
    start_year: Mapped[int | None] = mapped_column(Integer)

    direction: Mapped[Direction] = relationship(back_populates="groups")
    students: Mapped[list["Student"]] = relationship(back_populates="group")

    @property
    def current_semester(self) -> int | None:
        return current_semester(self.start_year) if self.start_year else None


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
    # ФИО преподавателя (у студента ФИО – в записи Student).
    full_name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, values_callable=lambda e: [m.value for m in e]))
    student_id: Mapped[int | None] = mapped_column(ForeignKey("student.id"), unique=True)
    # Выданный администратором пароль нужно сменить при первом входе.
    must_change_password: Mapped[bool] = mapped_column(default=False, server_default=false())
    # Увеличивается при смене/сбросе пароля – все ранее выданные токены перестают действовать.
    token_version: Mapped[int] = mapped_column(default=0, server_default="0")
    # Когда создана учётка: студент мог зарегистрироваться сам – администратору видно, когда.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    student: Mapped[Student | None] = relationship()


class LoginFailure(Base):
    """Неудачная попытка входа – для защиты от перебора паролей."""

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
    __table_args__ = (
        UniqueConstraint("direction_id", "code", name="uq_competency_direction_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    direction_id: Mapped[int] = mapped_column(ForeignKey("direction.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(16))  # "ОПК-5"
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
    direction: Mapped[Direction] = relationship()


class Indicator(Base):
    """Индикатор достижения компетенции, например ОПК-5.1."""

    __tablename__ = "indicator"
    __table_args__ = (
        UniqueConstraint("competency_id", "code", name="uq_indicator_competency_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competency.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(Text)

    competency: Mapped[Competency] = relationship(back_populates="indicators")


class Discipline(Base):
    __tablename__ = "discipline"
    __table_args__ = (
        UniqueConstraint("direction_id", "name", name="uq_discipline_direction_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    direction_id: Mapped[int] = mapped_column(ForeignKey("direction.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    # Индекс в учебном плане, например Б1.В.01.ДВ.01.01 (у заведенных вручную может не быть).
    code: Mapped[str | None] = mapped_column(String(32))
    kind: Mapped[DisciplineKind] = mapped_column(
        Enum(DisciplineKind, values_callable=lambda e: [m.value for m in e]),
        default=DisciplineKind.REGULAR,
        server_default=DisciplineKind.REGULAR.value,
    )

    competencies: Mapped[list[Competency]] = relationship(
        secondary=discipline_competency, back_populates="disciplines"
    )
    direction: Mapped[Direction] = relationship()

    @property
    def competency_ids(self) -> list[int]:
        return [c.id for c in self.competencies]


class CurriculumEntry(Base):
    """Строка учебного плана: в каких семестрах направления изучается дисциплина.

    Для оценки остаточных знаний важен последний семестр: в семестре N проверяются только
    дисциплины, завершённые раньше (last_semester < N).
    """

    __tablename__ = "curriculum_entry"
    __table_args__ = (
        UniqueConstraint("direction_id", "discipline_id", name="uq_curriculum_entry"),
        CheckConstraint(
            "first_semester >= 1 AND first_semester <= last_semester AND last_semester <= 12",
            name="ck_curriculum_semesters",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    direction_id: Mapped[int] = mapped_column(ForeignKey("direction.id", ondelete="CASCADE"))
    discipline_id: Mapped[int] = mapped_column(ForeignKey("discipline.id", ondelete="CASCADE"))
    first_semester: Mapped[int] = mapped_column(Integer)
    last_semester: Mapped[int] = mapped_column(Integer)
    # Преподаватель, который разрабатывает вопросы по дисциплине.
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"))

    direction: Mapped[Direction] = relationship()
    discipline: Mapped[Discipline] = relationship()
    teacher: Mapped["User | None"] = relationship()
    quotas: Mapped[list["CurriculumQuota"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


class CurriculumQuota(Base):
    """Сколько тестовых вопросов нужно разработать по компетенции дисциплины
    (по локальному нормативному акту: обычно 5, у практик 2–3)."""

    __tablename__ = "curriculum_quota"
    __table_args__ = (CheckConstraint("questions >= 1", name="ck_curriculum_quota_positive"),)

    entry_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_entry.id", ondelete="CASCADE"), primary_key=True
    )
    competency_id: Mapped[int] = mapped_column(
        ForeignKey("competency.id", ondelete="CASCADE"), primary_key=True
    )
    questions: Mapped[int] = mapped_column(Integer)

    entry: Mapped[CurriculumEntry] = relationship(back_populates="quotas")
    competency: Mapped["Competency"] = relationship()


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
    kind: Mapped[QuestionKind] = mapped_column(
        Enum(QuestionKind, values_callable=lambda e: [m.value for m in e])
    )
    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty, values_callable=lambda e: [m.value for m in e]),
        default=Difficulty.BASIC,
        server_default=Difficulty.BASIC.value,
    )

    competency: Mapped[Competency] = relationship()
    indicator: Mapped[Indicator | None] = relationship()
    discipline: Mapped[Discipline | None] = relationship()
    # Смысл вариантов зависит от типа задания:
    #   open     – допустимые ответы (сравниваются без учёта регистра);
    #   sequence – элементы в правильном порядке (position);
    #   matching – левый столбец (match – пара из правого) и правый столбец (match пуст;
    #              в правом могут быть лишние элементы).
    options: Mapped[list["AnswerOption"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="(AnswerOption.position, AnswerOption.id)",
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
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Задание на соответствие: элемент левого столбца ссылается на свою пару из правого.
    match_id: Mapped[int | None] = mapped_column(
        ForeignKey("answer_option.id", ondelete="SET NULL")
    )

    question: Mapped[Question] = relationship(back_populates="options")
    match: Mapped["AnswerOption | None"] = relationship(remote_side=[id])


# --- Тесты и прохождение ---------------------------------------------------


class Test(Base):
    __tablename__ = "test"
    __table_args__ = (UniqueConstraint("title", name="uq_test_title"),)
    __test__ = False  # не путать pytest

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    # Семестр, для которого собран тест (оценка остаточных знаний), если собирали по семестру.
    semester: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    disciplines: Mapped[list[Discipline]] = relationship(
        secondary=test_discipline, order_by="Discipline.name"
    )
    test_questions: Mapped[list["TestQuestion"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="TestQuestion.position"
    )

    assignments: Mapped[list["Assignment"]] = relationship(viewonly=True)

    @property
    def question_ids(self) -> list[int]:
        """Все вопросы теста без повторов (один вопрос может быть в нескольких вариантах)."""
        return list(dict.fromkeys(tq.question_id for tq in self.test_questions))

    @property
    def discipline_ids(self) -> list[int]:
        return [d.id for d in self.disciplines]

    @property
    def variant_count(self) -> int:
        return len({tq.variant for tq in self.test_questions})

    @property
    def questions_per_variant(self) -> int:
        """Сколько вопросов получает каждый студент (варианты одинаковой длины)."""
        return len(self.test_questions) // max(self.variant_count, 1)

    @property
    def group_ids(self) -> list[int]:
        return [a.group_id for a in self.assignments]


class TestQuestion(Base):
    __tablename__ = "test_question"
    __test__ = False

    test_id: Mapped[int] = mapped_column(
        ForeignKey("test.id", ondelete="CASCADE"), primary_key=True
    )
    # Номер варианта (с 1). Вопрос может входить в несколько вариантов одного теста.
    variant: Mapped[int] = mapped_column(Integer, primary_key=True, default=1, server_default="1")
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
    # Доставшийся студенту вариант теста (выбирается при первом открытии теста).
    variant: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[int | None] = mapped_column(Integer)
    max_score: Mapped[int | None] = mapped_column(Integer)
    # Черновик ответов (JSON) – сохраняется по ходу теста и стирается при сдаче.
    draft: Mapped[str | None] = mapped_column(Text)

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
    # Ответ студента (JSON): текст, порядок элементов или пары.
    response: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(default=False)

    attempt: Mapped[Attempt] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship()


class AppSetting(Base):
    """Настройки, которые администратор меняет в интерфейсе (ключ → значение)."""

    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))
