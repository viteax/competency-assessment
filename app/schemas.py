from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import CompetencyKind, Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Пользователи ---------------------------------------------------------


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6)
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


# --- Учебная часть ---------------------------------------------------------


class DirectionIn(BaseModel):
    code: str = Field(examples=["09.03.04"])
    name: str = Field(examples=["Программная инженерия"])


class DirectionOut(ORM, DirectionIn):
    id: int


class GroupIn(BaseModel):
    name: str = Field(examples=["ПИ-21"])
    direction_id: int


class GroupOut(ORM, GroupIn):
    id: int


class StudentIn(BaseModel):
    full_name: str
    group_id: int


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
    title: str
    discipline_id: int | None = None
    competency_ids: list[int] = Field(min_length=1)
    questions_per_competency: int = Field(default=5, ge=1, le=50)


class TestOut(ORM):
    id: int
    title: str
    discipline_id: int | None
    created_at: datetime
    question_ids: list[int]


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
