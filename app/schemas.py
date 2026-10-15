from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import CompetencyKind, Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Пользователи ---------------------------------------------------------


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    role: Role
    student_id: int | None = None

    @model_validator(mode="after")
    def student_link(self) -> "UserCreate":
        if (self.role == Role.STUDENT) != (self.student_id is not None):
            raise ValueError("student_id указывается только и обязательно для роли student")
        return self


class UserOut(ORM):
    id: int
    username: str
    role: Role
    student_id: int | None
    must_change_password: bool


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class PasswordReset(BaseModel):
    username: str
    password: str  # показывается один раз


# --- Учебная часть ---------------------------------------------------------


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


# --- Компетенции -----------------------------------------------------------


class IndicatorIn(BaseModel):
    code: str = Field(examples=["ОПК-5.1"])
    description: str


class IndicatorOut(ORM, IndicatorIn):
    id: int
    competency_id: int


class IndicatorCreate(IndicatorIn):
    competency_id: int


class CompetencyIn(BaseModel):
    code: str = Field(examples=["ОПК-5"])
    kind: CompetencyKind
    description: str
    indicators: list[IndicatorIn] = []


class CompetencyUpdate(BaseModel):
    code: str
    kind: CompetencyKind
    description: str


class CompetencyOut(ORM):
    id: int
    code: str
    kind: CompetencyKind
    description: str
    indicators: list[IndicatorOut]


class DisciplineIn(BaseModel):
    name: str = Field(examples=["Математика"])
    competency_ids: list[int] = []


class DisciplineOut(ORM):
    id: int
    name: str
    competency_ids: list[int]


class CurriculumEntryIn(BaseModel):
    direction_id: int
    discipline_id: int
    first_semester: int = Field(ge=1, le=12)
    last_semester: int = Field(ge=1, le=12)

    @model_validator(mode="after")
    def ordered(self) -> "CurriculumEntryIn":
        if self.first_semester > self.last_semester:
            raise ValueError("первый семестр не может быть позже последнего")
        return self


class CurriculumEntryOut(ORM, CurriculumEntryIn):
    id: int


# --- Профстандарт ----------------------------------------------------------


class LaborFunctionIn(BaseModel):
    code: str = Field(examples=["A/01.3"])
    name: str
    competency_ids: list[int] = []


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


# --- Банк вопросов ---------------------------------------------------------


class AnswerOptionIn(BaseModel):
    text: str
    is_correct: bool = False


class AnswerOptionOut(ORM, AnswerOptionIn):
    id: int


class AnswerOptionUpdate(AnswerOptionIn):
    id: int | None = None  # None — новый вариант


class QuestionIn(BaseModel):
    competency_id: int
    indicator_id: int | None = None
    discipline_id: int | None = None
    text: str = Field(min_length=1)
    options: list[AnswerOptionIn] = Field(min_length=2)

    @model_validator(mode="after")
    def exactly_one_correct(self) -> "QuestionIn":
        if sum(o.is_correct for o in self.options) != 1:
            raise ValueError("ровно один вариант ответа должен быть правильным")
        return self


class QuestionUpdate(QuestionIn):
    options: list[AnswerOptionUpdate] = Field(min_length=2)


class QuestionOut(ORM):
    id: int
    competency_id: int
    indicator_id: int | None
    discipline_id: int | None
    text: str
    options: list[AnswerOptionOut]
    in_use: bool  # входит в собранные тесты: менять можно только формулировки


# --- Тесты -----------------------------------------------------------------


class TestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # опечатка в поле не должна молча игнорироваться

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    competency_ids: list[int] = Field(min_length=1)
    # Вопросы берутся только из этих дисциплин; пусто — из любых.
    discipline_ids: list[int] = []
    questions_per_competency: int = Field(default=5, ge=1, le=50)
    semester: int | None = Field(default=None, ge=1, le=12)


class TestOut(ORM):
    id: int
    title: str
    semester: int | None
    discipline_ids: list[int]
    created_at: datetime
    question_ids: list[int]
    variant_count: int
    questions_per_variant: int
    group_ids: list[int]  # каким группам уже назначен


class TestVariantOut(BaseModel):
    variant: int
    questions: list[QuestionOut]


class TestAssignmentOut(BaseModel):
    id: int
    group_id: int
    group_name: str
    created_at: datetime
    started: int  # студентов открыли тест
    finished: int  # и сдали


class TestDetail(TestOut):
    variants: list[TestVariantOut]
    assignments: list[TestAssignmentOut]


class PlanDiscipline(BaseModel):
    id: int
    name: str
    first_semester: int
    last_semester: int
    competency_ids: list[int]


class QuestionCount(BaseModel):
    competency_id: int
    discipline_id: int
    count: int


class AssemblyPlan(BaseModel):
    """Что доступно для оценки остаточных знаний группы в семестре."""

    group_id: int
    semester: int
    finished: list[PlanDiscipline]  # завершены до этого семестра — из них берутся вопросы
    not_finished: list[PlanDiscipline]  # ещё изучаются или впереди
    unplanned: list[str]  # дисциплины, у которых семестры не указаны ни в одном учебном плане
    question_counts: list[QuestionCount]  # вопросов в банке по завершённым дисциплинам


class AssignmentIn(BaseModel):
    test_id: int
    group_id: int


class AssignmentOut(ORM, AssignmentIn):
    id: int
    created_at: datetime


class AttemptSummary(ORM):
    id: int
    finished_at: datetime | None
    score: int | None
    max_score: int | None


class StudentAssignmentOut(BaseModel):
    id: int
    title: str
    question_count: int
    created_at: datetime
    attempt: AttemptSummary | None


# Вопрос в том виде, в каком его видит студент: без признака правильности.
class StudentOptionOut(ORM):
    id: int
    text: str


class StudentQuestionOut(ORM):
    id: int
    text: str
    options: list[StudentOptionOut]


class AttemptStart(BaseModel):
    assignment_id: int


class AttemptStarted(BaseModel):
    attempt_id: int
    title: str
    questions: list[StudentQuestionOut]


class AnswerIn(BaseModel):
    question_id: int
    option_id: int


class AttemptSubmit(BaseModel):
    answers: list[AnswerIn]


class AttemptResult(BaseModel):
    attempt_id: int
    score: int
    max_score: int
    finished_at: datetime


# --- Отчёты ----------------------------------------------------------------


class CompetencyResult(BaseModel):
    competency_id: int
    code: str
    kind: CompetencyKind
    correct: int
    total: int
    ratio: float
    mastered: bool


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


class GroupCompetencyReport(BaseModel):
    group_id: int
    name: str
    students: list[StudentCompetencyReport]


# --- Импорт компетенций ----------------------------------------------------

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


# --- Импорт студентов ------------------------------------------------------


class StudentImportRowIn(BaseModel):
    full_name: str = Field(min_length=1)
    email: str | None = None
    external_id: str | None = Field(default=None, max_length=64)
    login: str | None = None
    group: str | None = None


class StudentImportRow(StudentImportRowIn):
    full_name: str  # в предпросмотре может быть пустым — тогда это проблема строки
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
