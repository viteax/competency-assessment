"""Таблица со списком студентов: чтение файла, распознавание колонок, разбор строк.

Формат выгрузки заранее неизвестен (участники курса Moodle, журнал оценок, список из
деканата), поэтому колонки определяются по заголовкам, а администратор может переназначить
их вручную. Модуль не обращается к БД.
"""

import re
from dataclasses import dataclass

from app.errors import DomainError
from app.services import files

FIELDS = (
    "full_name",
    "last_name",
    "first_name",
    "middle_name",
    "email",
    "external_id",
    "login",
    "group",
    "program",
    "role",
)

# Порядок важен: более конкретные заголовки проверяются раньше общих.
_HEADER_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "full_name",
        re.compile(
            r"^(фио|ф\.\s?и\.\s?о\.?|имя\s*/\s*фамилия|фамилия\s*/?\s*имя|"
            r"полное имя|full ?name|студент|обучающийся|слушатель)"
        ),
    ),
    ("email", re.compile(r"(почт|e-?mail)")),
    (
        "external_id",
        re.compile(
            r"(индивидуальный номер|id ?number|idnumber|зач[её]тн|"
            r"номер студ|табельный|^id$)"
        ),
    ),
    ("login", re.compile(r"(логин|username|имя пользователя)")),
    ("middle_name", re.compile(r"(отчество|middle ?name)")),
    ("last_name", re.compile(r"(фамилия|last ?name|surname)")),
    ("first_name", re.compile(r"(^имя|first ?name)")),
    ("group", re.compile(r"(групп|group|^отдел|department)")),
    ("program", re.compile(r"(образовательн|программ|направлен|специальност|профил)")),
    ("role", re.compile(r"(^рол|^role)")),
]

_STUDENT_ROLE = re.compile(r"(студент|student|обучающ|слушател)", re.IGNORECASE)

Mapping = dict[str, int | None]


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]


@dataclass
class ParsedRow:
    full_name: str
    email: str
    external_id: str
    login: str
    group: str
    program: str  # образовательная программа (направление): «09.03.04 Программная инженерия»
    role: str

    @property
    def is_student(self) -> bool:
        """Роль похожа на студенческую (или колонки ролей нет)."""
        return not self.role or bool(_STUDENT_ROLE.search(self.role))


def read_table(filename: str, data: bytes) -> Table:
    ext = files.file_kind(filename, data, (".csv", ".txt", ".xlsx"))
    with files.reading():
        raw = files.xlsx_rows(data) if ext == ".xlsx" else files.csv_rows(files.decode_text(data))
    rows = [[c.strip() for c in r] for r in raw if any(c.strip() for c in r)]
    if not rows:
        raise DomainError("файл пустой")
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    return Table(headers=rows[0], rows=rows[1:])


def guess_mapping(headers: list[str]) -> Mapping:
    mapping: Mapping = dict.fromkeys(FIELDS)
    for index, header in enumerate(headers):
        h = re.sub(r"\s+", " ", header.lower()).strip()
        for field, rule in _HEADER_RULES:
            if mapping[field] is None and rule.search(h):
                mapping[field] = index
                break
    # Если ФИО собрано в одну колонку, отдельные части не нужны.
    if mapping["full_name"] is not None:
        mapping["last_name"] = mapping["first_name"] = mapping["middle_name"] = None
    return mapping


def parse_row(row: list[str], m: Mapping) -> ParsedRow:
    def cell(field: str) -> str:
        index = m.get(field)
        return row[index].strip() if index is not None and index < len(row) else ""

    full_name = cell("full_name") or " ".join(
        p for p in (cell("last_name"), cell("first_name"), cell("middle_name")) if p
    )
    return ParsedRow(
        full_name=re.sub(r"\s+", " ", full_name).strip(),
        email=cell("email").lower(),
        external_id=cell("external_id") or cell("login"),
        login=cell("login"),
        # В Moodle в колонке «Группы» может быть несколько групп через запятую – берём первую.
        group=re.split(r"[,;]", cell("group"))[0].strip(),
        program=cell("program"),
        role=cell("role"),
    )
