"""Загрузка учебного плана из Excel-выгрузки программы «Планы» (файл вида *.plx.xlsx).

Из листов берется все, что нужно справочникам направления:
  «Титул»       – код и название направления, профиль, год начала подготовки;
  «Компетенции» – коды и формулировки компетенций;
  «План»        – дисциплины: индекс, название, семестры, компетенции. Статус – по индексу:
                  ДВ – по выбору, ФТД – факультатив, Б2 – практика. Модули (строки, у которых
                  есть вложенные) и ГИА (Б3) пропускаются;
  профстандарты – лист с колонками «Индекс», «Наименование», «Компетенции» и кодами ТФ
                  (обычно «Компетенции(3)»): профстандарты, ОТФ, ТФ и нужные для ТФ
                  компетенции.
Колонки ищутся по заголовкам, а не по номерам: выгрузки разных лет немного отличаются.
Сначала предпросмотр, потом сохранение; ничего не удаляется, повторная загрузка того же плана
ничего не меняет.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.errors import DomainError
from app.services import files
from app.services.wording import clean_wording, differs

PLAN_SHEET, COMPETENCY_SHEET, TITLE_SHEET = "план", "компетенции", "титул"

_COMPETENCY = re.compile(r"^(УК|ОПК|ПК)-(\d+)$")
_DIRECTION = re.compile(r"^\d{2}\.\d{2}\.\d{2}$")
_STANDARD = re.compile(r"^\d{2}\.\d{3}$")
_GENERAL = re.compile(r"^[A-ZА-ЯЁ]$")
_FUNCTION = re.compile(r"^[A-ZА-ЯЁ]/\d{2}\.(\d{1,2})$")
_SEMESTER = re.compile(r"^семестр\s*(\d{1,2})$", re.IGNORECASE)

# Кириллические буквы, похожие на латинские: в кодах ОТФ и ТФ их пишут вперемешку.
_LATIN = str.maketrans("АВЕКМНОРСТХ", "ABEKMHOPCTX")


def same_code(code: str) -> str:
    """Код ОТФ или ТФ для сравнения: «С/01.6» кириллицей и «C/01.6» латиницей – одно и то же."""
    return code.strip().upper().translate(_LATIN)


@dataclass
class PlanCompetency:
    code: str
    description: str

    @property
    def kind(self) -> models.CompetencyKind:
        return models.CompetencyKind(self.code.split("-")[0])


@dataclass
class PlanDiscipline:
    code: str  # индекс в плане
    name: str
    kind: models.DisciplineKind
    first_semester: int | None
    last_semester: int | None
    competencies: list[str]


@dataclass
class PlanFunction:
    code: str
    name: str
    competencies: list[str]


@dataclass
class PlanGeneral:
    code: str
    name: str
    level: int
    functions: list[PlanFunction] = field(default_factory=list)


@dataclass
class PlanStandard:
    code: str
    name: str
    generals: list[PlanGeneral] = field(default_factory=list)


@dataclass
class ParsedPlan:
    direction_code: str
    direction_name: str
    profile: str | None
    year: int | None
    competencies: dict[str, PlanCompetency]
    disciplines: list[PlanDiscipline]
    standards: list[PlanStandard]
    skipped: list[str]  # что в плане есть, но не загружается (ГИА)
    warnings: list[str]


# --- чтение листов ------------------------------------------------------------------


def _norm(text: str) -> str:
    """Заголовок колонки для сравнения: «Экза мен» и «Зачет с оц.» – как «экзамен», «зачетсоц.»."""
    return re.sub(r"\s+", "", text).lower().replace("ё", "е")


def _clean(text: str) -> str:
    return " ".join(text.replace("_x000d_", " ").split())


def _sheet(sheets: dict[str, list[list[str]]], name: str) -> list[list[str]] | None:
    return next((rows for title, rows in sheets.items() if _norm(title) == name), None)


def is_plan(sheets: dict[str, list[list[str]]]) -> bool:
    """Похоже ли на выгрузку учебного плана из «Планов»: есть листы «План» и «Компетенции»."""
    return _sheet(sheets, PLAN_SHEET) is not None and _sheet(sheets, COMPETENCY_SHEET) is not None


def _header(rows: list[list[str]], *names: str) -> tuple[int, dict[str, int]]:
    """Строка заголовков, в которой есть все names, и номера колонок по заголовкам."""
    wanted = [_norm(n) for n in names]
    for i, row in enumerate(rows[:15]):
        columns: dict[str, int] = {}
        for j, cell in enumerate(row):
            columns.setdefault(_norm(cell), j)
        if all(n in columns for n in wanted):
            return i, columns
    raise DomainError(f"не найдены колонки {', '.join(f'«{n}»' for n in names)}")


def _first(row: list[str], before: int) -> str:
    """Первая непустая ячейка левее колонки before: коды стоят в разных колонках по уровню."""
    return next((cell.strip() for cell in row[:before] if cell.strip()), "")


def _codes(text: str) -> list[str]:
    codes = []
    for part in re.split(r"[;,\s]+", text):
        m = _COMPETENCY.match(part.strip())
        if m:
            codes.append(f"{m[1]}-{int(m[2])}")
    return list(dict.fromkeys(codes))


def _title(rows: list[list[str]]) -> tuple[str, str, str | None, int | None]:
    """Код и название направления, профиль и год начала подготовки с листа «Титул»."""
    code = name = ""
    profile = year = None
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            text = _clean(cell)
            if not code and _DIRECTION.match(text):
                code = text
                # Название – ниже в той же колонке.
                below = [_clean(r[j]) for r in rows[i + 1 : i + 5] if j < len(r)]
                name = next((b for b in below if b and not _DIRECTION.match(b)), "")
            elif profile is None and text.lower().startswith("профиль"):
                rest = [_clean(c) for c in row[j + 1 :] if _clean(c)]
                profile = rest[0] if rest else None
            elif year is None and "год начала подготовки" in text.lower():
                rest = [_clean(c) for c in row[j + 1 :] if _clean(c)]
                year = int(rest[0]) if rest and rest[0].isdigit() else None
    if not code:
        raise DomainError("на листе «Титул» не найден код направления (например, 09.03.01)")
    return code, name or code, profile, year


def _competencies(rows: list[list[str]], warnings: list[str]) -> dict[str, PlanCompetency]:
    top, columns = _header(rows, "Индекс", "Содержание")
    content = columns[_norm("Содержание")]
    result: dict[str, PlanCompetency] = {}
    for row in rows[top + 1 :]:
        code = _first(row, content)
        if not _COMPETENCY.match(code):
            continue  # строки дисциплин, «Тип задач профессиональной деятельности»
        description = clean_wording(row[content] if content < len(row) else "")
        if not description:
            warnings.append(f"{code}: на листе «Компетенции» нет формулировки")
        result[code] = PlanCompetency(code=code, description=description)
    return result


def _semester_blocks(rows: list[list[str]], top: int) -> list[tuple[int, int, int]]:
    """Колонки семестров в шапке плана: (номер семестра, первая колонка, следующая за последней)."""
    starts = sorted(
        (j, int(m[1]))
        for row in rows[: top + 1]
        for j, cell in enumerate(row)
        if (m := _SEMESTER.match(cell.strip()))
    )
    if not starts:
        return []
    width = starts[1][0] - starts[0][0] if len(starts) > 1 else 1
    ends = [j for j, _ in starts[1:]] + [starts[-1][0] + width]
    return [(n, j, end) for (j, n), end in zip(starts, ends, strict=True)]


def _number(text: str) -> float:
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return 0.0


def _discipline_kind(code: str) -> models.DisciplineKind:
    if code.startswith("ФТД"):
        return models.DisciplineKind.OPTIONAL
    if ".ДВ." in code:
        return models.DisciplineKind.ELECTIVE
    if code.startswith("Б2"):
        return models.DisciplineKind.PRACTICE
    return models.DisciplineKind.REGULAR


def _control_semesters(row: list[str], columns: dict[str, int]) -> list[int]:
    """Семестры из колонок форм контроля: «125» – 1, 2 и 5-й; после 9-го – буквы A, B, C."""
    result = set()
    for name in ("экзамен", "зачет", "зачетсоц.", "кп", "кр"):
        j = columns.get(name)
        for ch in row[j] if j is not None and j < len(row) else "":
            if ch.isdigit() and ch != "0":
                result.add(int(ch))
            elif ch.upper() in "ABC":
                result.add(10 + "ABC".index(ch.upper()))
    return sorted(result)


def _disciplines(
    rows: list[list[str]], warnings: list[str], skipped: list[str]
) -> list[PlanDiscipline]:
    top, columns = _header(rows, "Индекс", "Наименование")
    index, title = columns["индекс"], columns["наименование"]
    competencies = columns.get("компетенции")
    blocks = _semester_blocks(rows, top)

    def cell(row: list[str], j: int | None) -> str:
        return _clean(row[j]) if j is not None and j < len(row) else ""

    lines = [(cell(row, index), cell(row, title), row) for row in rows[top + 1 :]]
    lines = [line for line in lines if line[0] and line[1]]
    codes = [code for code, _, _ in lines]
    by_name: dict[str, PlanDiscipline] = {}
    for code, name, row in lines:
        if any(other.startswith(code + ".") for other in codes):
            continue  # модуль или блок дисциплин по выбору – дисциплины в нем отдельными строками
        if code.startswith("Б3"):
            skipped.append(f"{code} {name}")  # ГИА: по ней тесты не проводятся
            continue
        semesters = [
            n for n, start, end in blocks if any(_number(v) > 0 for v in row[start:end])
        ] or _control_semesters(row, columns)
        if not semesters:
            warnings.append(f"{code} «{name}»: в плане не найдены семестры – укажите их сами")
        discipline = PlanDiscipline(
            code=code,
            name=name,
            kind=_discipline_kind(code),
            first_semester=min(semesters) if semesters else None,
            last_semester=max(semesters) if semesters else None,
            competencies=_codes(cell(row, competencies)),
        )
        same = by_name.get(name)
        if same is None:
            by_name[name] = discipline
            continue
        # Одна дисциплина в двух строках плана (например, в разных модулях) – одна дисциплина.
        warnings.append(f"«{name}» в плане дважды ({same.code} и {code}) – объединено")
        known = [n for n in (same.first_semester, discipline.first_semester) if n]
        if known:
            same.first_semester = min(known)
            same.last_semester = max(n for n in (same.last_semester, discipline.last_semester) if n)
        same.competencies = list(dict.fromkeys(same.competencies + discipline.competencies))
    return list(by_name.values())


def _sentence_case(text: str) -> str:
    """«СИСТЕМНЫЙ АНАЛИТИК» → «Системный аналитик»; обычный текст не меняется."""
    return text[:1] + text[1:].lower() if text.isupper() else text


def _standards_sheet(sheets: dict[str, list[list[str]]]) -> list[list[str]] | None:
    for rows in sheets.values():
        try:
            top, columns = _header(rows, "Индекс", "Наименование", "Компетенции")
        except DomainError:
            continue
        before = columns["наименование"]
        if any(_FUNCTION.match(_first(row, before)) for row in rows[top + 1 :]):
            return rows
    return None


def _standards(rows: list[list[str]]) -> list[PlanStandard]:
    top, columns = _header(rows, "Индекс", "Наименование", "Компетенции")
    title, links = columns["наименование"], columns["компетенции"]
    result: list[PlanStandard] = []
    standard: PlanStandard | None = None
    general: PlanGeneral | None = None
    for row in rows[top + 1 :]:
        code = _first(row, title)
        name = _clean(row[title]) if title < len(row) else ""
        if _STANDARD.match(code):
            standard = PlanStandard(code=code, name=_sentence_case(name))
            result.append(standard)
            general = None
        elif _GENERAL.match(code) and standard is not None:
            general = PlanGeneral(code=code, name=name, level=0)
            standard.generals.append(general)
        elif (m := _FUNCTION.match(code)) and general is not None:
            general.level = general.level or int(m[1])  # уровень ОТФ – по кодам ее ТФ
            competencies = _codes(row[links] if links < len(row) else "")
            general.functions.append(PlanFunction(code=code, name=name, competencies=competencies))
    for s in result:
        for g in s.generals:
            g.level = g.level or 6
    return result


def parse(data: bytes) -> ParsedPlan:
    with files.reading():
        sheets = files.xlsx_sheets(data)
    if not is_plan(sheets):
        raise DomainError(
            "это не учебный план из «Планов»: нужны листы «Титул», «План» и «Компетенции»"
        )
    warnings: list[str] = []
    skipped: list[str] = []
    title = _sheet(sheets, TITLE_SHEET)
    if title is None:
        raise DomainError("в файле нет листа «Титул» с кодом направления")
    code, name, profile, year = _title(title)
    competencies = _competencies(_sheet(sheets, COMPETENCY_SHEET), warnings)
    disciplines = _disciplines(_sheet(sheets, PLAN_SHEET), warnings, skipped)
    standards_rows = _standards_sheet(sheets)
    standards = _standards(standards_rows) if standards_rows else []
    if standards_rows is None:
        warnings.append("лист с профстандартами (ОТФ, ТФ и компетенции) не найден")

    known = set(competencies)
    used = [c for d in disciplines for c in d.competencies] + [
        c for s in standards for g in s.generals for f in g.functions for c in f.competencies
    ]
    for missing in sorted(set(used) - known):
        warnings.append(f"{missing} нет на листе «Компетенции» – связи с ней пропущены")
    return ParsedPlan(
        direction_code=code,
        direction_name=name,
        profile=profile,
        year=year,
        competencies=competencies,
        disciplines=disciplines,
        standards=standards,
        skipped=skipped,
        warnings=warnings,
    )


# --- сравнение с базой --------------------------------------------------------------


@dataclass
class _Existing:
    direction: models.Direction | None
    competencies: dict[str, models.Competency]
    disciplines: dict[str, models.Discipline]
    entries: dict[int, models.CurriculumEntry]  # id дисциплины → строка плана
    standards: dict[str, models.ProfStandard]


def _existing(session: Session, plan: ParsedPlan) -> _Existing:
    direction = session.scalar(
        select(models.Direction).where(models.Direction.code == plan.direction_code)
    )
    competencies, disciplines, entries = {}, {}, {}
    if direction is not None:
        competencies = {
            c.code: c
            for c in session.scalars(
                select(models.Competency).where(models.Competency.direction_id == direction.id)
            )
        }
        disciplines = {
            d.name: d
            for d in session.scalars(
                select(models.Discipline)
                .where(models.Discipline.direction_id == direction.id)
                .options(selectinload(models.Discipline.competencies))
            )
        }
        entries = {
            e.discipline_id: e
            for e in session.scalars(
                select(models.CurriculumEntry).where(
                    models.CurriculumEntry.direction_id == direction.id
                )
            )
        }
    standards = {
        s.code: s
        for s in session.scalars(
            select(models.ProfStandard)
            .where(models.ProfStandard.code.in_([s.code for s in plan.standards]))
            .options(
                selectinload(models.ProfStandard.general_functions)
                .selectinload(models.GeneralLaborFunction.functions)
                .selectinload(models.LaborFunction.competencies)
            )
        )
    }
    return _Existing(direction, competencies, disciplines, entries, standards)


def _find[T: (models.GeneralLaborFunction, models.LaborFunction)](
    items: list[T], code: str
) -> T | None:
    return next((i for i in items if same_code(i.code) == same_code(code)), None)


def _range(first: int | None, last: int | None) -> str:
    return "–" if first is None else str(first) if first == last else f"{first}–{last}"


def _discipline_changes(
    plan: PlanDiscipline,
    found: models.Discipline,
    entry: models.CurriculumEntry | None,
    known: dict[str, PlanCompetency],
) -> list[str]:
    """Что поменяется у существующей дисциплины (known – компетенции с листа «Компетенции»:
    связи с остальными не создаются)."""
    changes = []
    if found.code != plan.code:
        changes.append(f"индекс {found.code or '–'} → {plan.code}")
    if found.kind != plan.kind:
        changes.append("статус")
    if plan.first_semester is not None and (
        entry is None
        or (entry.first_semester, entry.last_semester) != (plan.first_semester, plan.last_semester)
    ):
        before = _range(entry.first_semester, entry.last_semester) if entry else "–"
        changes.append(f"семестры {before} → {_range(plan.first_semester, plan.last_semester)}")
    linked = {c.code for c in found.competencies}
    added = [c for c in plan.competencies if c not in linked and c in known]
    if added:
        changes.append("+ " + ", ".join(added))
    return changes


def preview(session: Session, filename: str, plan: ParsedPlan) -> schemas.PlanPreview:
    have = _existing(session, plan)
    competencies = []
    for pc in plan.competencies.values():
        current = have.competencies.get(pc.code)
        status = (
            "new"
            if current is None
            else "update"
            if differs(pc.description, current.description)
            else "same"
        )
        competencies.append(
            schemas.PlanCompetencyItem(
                code=pc.code,
                description=pc.description,
                status=status,
                existing_description=current.description if current else None,
            )
        )
    disciplines = []
    for pd in plan.disciplines:
        found = have.disciplines.get(pd.name)
        changes = (
            _discipline_changes(pd, found, have.entries.get(found.id), plan.competencies)
            if found is not None
            else []
        )
        disciplines.append(
            schemas.PlanDisciplineItem(
                code=pd.code,
                name=pd.name,
                kind=pd.kind,
                first_semester=pd.first_semester,
                last_semester=pd.last_semester,
                competency_codes=pd.competencies,
                status="new" if found is None else "update" if changes else "same",
                changes=changes,
            )
        )
    standards = []
    for ps in plan.standards:
        standard = have.standards.get(ps.code)
        generals = []
        for pg in ps.generals:
            general = _find(standard.general_functions, pg.code) if standard else None
            functions = []
            for pf in pg.functions:
                function = _find(general.functions, pf.code) if general else None
                linked = {
                    c.code
                    for c in (function.competencies if function else [])
                    if have.direction and c.direction_id == have.direction.id
                }
                fresh = [c for c in pf.competencies if c not in linked and c in plan.competencies]
                functions.append(
                    schemas.PlanFunctionItem(
                        code=pf.code,
                        name=pf.name,
                        competency_codes=pf.competencies,
                        status="new" if function is None else "update" if fresh else "same",
                    )
                )
            generals.append(
                schemas.PlanGeneralItem(
                    code=pg.code,
                    name=pg.name,
                    level=pg.level,
                    exists=general is not None,
                    functions=functions,
                )
            )
        standards.append(
            schemas.PlanStandardItem(
                code=ps.code,
                name=ps.name,
                exists=standard is not None,
                general_functions=generals,
            )
        )
    return schemas.PlanPreview(
        filename=filename,
        direction=schemas.PlanDirection(
            code=plan.direction_code,
            name=have.direction.name if have.direction else plan.direction_name,
            profile=plan.profile,
            year=plan.year,
            id=have.direction.id if have.direction else None,
        ),
        competencies=competencies,
        disciplines=disciplines,
        standards=standards,
        skipped=plan.skipped,
        warnings=plan.warnings,
    )


# --- сохранение ----------------------------------------------------------------------


def apply(session: Session, plan: ParsedPlan, overwrite_descriptions: bool) -> schemas.PlanResult:
    """Создает недостающее и дополняет существующее; ничего не удаляет. Формулировки
    существующих компетенций меняются только с overwrite_descriptions; названия
    профстандартов, ОТФ и ТФ, преподаватели и квоты в учебном плане не трогаются."""
    have = _existing(session, plan)
    result = schemas.PlanResult(direction_id=0)
    direction = have.direction
    if direction is None:
        direction = models.Direction(code=plan.direction_code, name=plan.direction_name)
        session.add(direction)
        result.created_direction = True

    competencies: dict[str, models.Competency] = {}
    for pc in plan.competencies.values():
        competency = have.competencies.get(pc.code)
        if competency is None:
            if not pc.description:
                continue  # без формулировки не создаем: предупреждение уже в предпросмотре
            competency = models.Competency(
                direction=direction, code=pc.code, kind=pc.kind, description=pc.description
            )
            session.add(competency)
            result.created_competencies += 1
        elif overwrite_descriptions and differs(pc.description, competency.description):
            competency.description = pc.description
            result.updated_competencies += 1
        competencies[pc.code] = competency

    for pd in plan.disciplines:
        discipline = have.disciplines.get(pd.name)
        entry = have.entries.get(discipline.id) if discipline is not None else None
        if discipline is None:
            discipline = models.Discipline(direction=direction, name=pd.name)
            session.add(discipline)
            result.created_disciplines += 1
        elif _discipline_changes(pd, discipline, entry, plan.competencies):
            result.updated_disciplines += 1
        discipline.code = pd.code
        discipline.kind = pd.kind
        for code in pd.competencies:
            competency = competencies.get(code)
            if competency is not None and competency not in discipline.competencies:
                discipline.competencies.append(competency)
        if pd.first_semester is None:
            continue
        if entry is None:
            session.add(
                models.CurriculumEntry(
                    direction=direction,
                    discipline=discipline,
                    first_semester=pd.first_semester,
                    last_semester=pd.last_semester,
                )
            )
        else:
            entry.first_semester, entry.last_semester = pd.first_semester, pd.last_semester

    for ps in plan.standards:
        standard = have.standards.get(ps.code)
        if standard is None:
            standard = models.ProfStandard(code=ps.code, name=ps.name)
            session.add(standard)
            result.created_standards += 1
        for pg in ps.generals:
            general = _find(standard.general_functions, pg.code)
            if general is None:
                general = models.GeneralLaborFunction(
                    code=pg.code, name=pg.name, qualification_level=pg.level
                )
                standard.general_functions.append(general)
                result.created_general_functions += 1
            for pf in pg.functions:
                function = _find(general.functions, pf.code)
                if function is None:
                    function = models.LaborFunction(code=pf.code, name=pf.name)
                    general.functions.append(function)
                    result.created_labor_functions += 1
                for code in pf.competencies:
                    competency = competencies.get(code)
                    if competency is not None and competency not in function.competencies:
                        function.competencies.append(competency)
                        result.linked_labor_functions += 1

    session.commit()
    result.direction_id = direction.id
    return result
