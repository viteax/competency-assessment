"""Импорт компетенций и индикаторов из файлов ОПОП / РПД.

Структура таких документов у вузов разная (таблица «код – формулировка – индикаторы»,
сплошной текст, матрица компетенций в Excel), поэтому разбор не завязан на вёрстку:
из файла извлекается текст, а в нём ищутся коды вида УК-1, ОПК-5, ПК-2 и коды
индикаторов (УК-1.1, ИУК-1.1, ИД-1.УК-1, ИД-1 ОПК-5 …). Формулировка – текст после
кода до следующего кода. Результат показывается администратору для проверки и только
потом сохраняется.

Исключение – таблицы в PDF: текстовый слой PDF перемешивает ячейки соседних колонок,
поэтому там текст сначала раскладывается по колонкам (см. _pdf_text).
"""

import io
import re
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.errors import DomainError
from app.services import files, plan_import
from app.services.common import code_key, get_or_404
from app.services.wording import clean_wording, differs

SUPPORTED = (".docx", ".xlsx", ".pdf", ".txt")

_DASH = r"[-‑–\u2014]"  # дефис, неразрывный дефис, среднее и длинное тире
_KIND = r"(?P<{name}>УК|ОПК|ПК)"
_NOT_LETTER = r"(?<![А-Яа-яЁёA-Za-z])"

_CODE_RE = re.compile(
    "|".join(
        [
            # ИД-1.УК-1, ИД-1 ОПК-5, ИД1.ПК-2 – номер индикатора перед кодом компетенции
            rf"{_NOT_LETTER}ИДК?\s?{_DASH}?\s?(?P<a_ind>\d+)\s?[.\s]?\s?"
            rf"{_KIND.format(name='a_kind')}\s?{_DASH}\s?(?P<a_num>\d+)",
            # УК-1.1, ИУК-1.1, ИД-УК-1.1, ИДК-ОПК-5.2
            rf"{_NOT_LETTER}(?:ИДК?\s?{_DASH}?\s?|И)?{_KIND.format(name='b_kind')}"
            rf"\s?{_DASH}\s?(?P<b_num>\d+)\.(?P<b_ind>\d+)",
            # УК-1, ОПК-5
            rf"{_NOT_LETTER}{_KIND.format(name='c_kind')}\s?{_DASH}\s?(?P<c_num>\d+)(?![.,]?\d)",
        ]
    )
)

_DISCIPLINE_RE = re.compile(
    r"дисциплин[аыу]?\s*(?:\(\s*модул[яь]\s*\)\s*)?[«\"“](?P<name>[^»\"”\n]{2,200})[»\"”]",
    re.IGNORECASE,
)

# Где формулировка точно кончилась: пустая строка или шапка следующей таблицы.
_END_RE = re.compile(r"\n\s*\n|код и наименование|наименование категории", re.IGNORECASE)


@dataclass
class ParsedCompetency:
    code: str
    kind: models.CompetencyKind
    description: str = ""
    indicators: dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    discipline_name: str | None
    competencies: dict[str, ParsedCompetency]


# --- извлечение текста ------------------------------------------------------


def extract_text(filename: str, data: bytes) -> str:
    ext = files.file_kind(filename, data, SUPPORTED)
    with files.reading():
        if ext == ".docx":
            return files.docx_text(data)
        if ext == ".xlsx":
            sheets = files.xlsx_sheets(data)
            if plan_import.is_plan(sheets):
                raise DomainError(
                    "это учебный план из «Планов» – загрузите его на вкладке «Загрузка УП»: "
                    "оттуда берутся и компетенции, и дисциплины с семестрами, и ТФ"
                )
            # Строка таблицы – отдельный абзац: формулировка не перетекает в соседние строки
            # и на другие листы (parse_text обрывает ее на пустой строке).
            return "\n\n".join(
                "\n".join(cell for cell in row if cell.strip())
                for rows in sheets.values()
                for row in rows
            )
        if ext == ".pdf":
            return _pdf_text(data)
        return files.decode_text(data)


# Таблица «группа | компетенция | индикаторы | …» в PDF. Ячейки идут колонками, и обычное
# извлечение текста склеивает соседние ячейки построчно: формулировка компетенции рвется
# текстом индикаторов, в нее попадают колонки групп и профстандартов, а хвост ячейки после
# разрыва страницы уходит за колонтитул. Поэтому страница читается с сохранением
# расположения, колонки компетенций и индикаторов находятся по отступу их кодов, и текст
# собирается по колонкам; остальные колонки и строки только из цифр (колонтитулы)
# отбрасываются.

_SEGMENT_RE = re.compile(r"\S+(?: \S+)*")  # кусок строки до разрыва в два пробела и больше
_COLUMN_SLACK = 3  # на сколько символов может «гулять» начало колонки


def _code_columns(lines: list[str], previous: tuple[int, int] | None) -> tuple[int, int] | None:
    """Отступы колонки компетенций и колонки индикаторов, если страница – такая таблица.

    На странице-продолжении может не быть кодов одного вида (только индикаторы конца
    строки таблицы) – тогда отступ этой колонки берется с прошлой страницы. Страница совсем
    без кодов таблицей не считается.
    """
    competencies: Counter[int] = Counter()
    indicators: Counter[int] = Counter()
    for line in lines:
        for segment in _SEGMENT_RE.finditer(line):
            m = _CODE_RE.match(segment.group())
            if m:
                target = indicators if m["a_kind"] or m["b_kind"] else competencies
                target[segment.start()] += 1
    if not competencies and not indicators:
        return None
    competency_x = competencies.most_common(1)[0][0] if competencies else None
    indicator_x = indicators.most_common(1)[0][0] if indicators else None
    if previous is not None:
        competency_x = previous[0] if competency_x is None else competency_x
        indicator_x = previous[1] if indicator_x is None else indicator_x
    if competency_x is None or indicator_x is None:
        return None
    # Коды в одной колонке – это не таблица с колонками, а список: читаем как обычно.
    return (competency_x, indicator_x) if indicator_x - competency_x > 10 else None


def _table_cells(line: str, competency_x: int, indicator_x: int) -> tuple[str, str]:
    """Куски строки в колонках компетенций и индикаторов. Строка, в которой кусок попадает
    между колонками, – не строка таблицы, а абзац, выровненный по ширине: его пропускаем."""
    competency, indicator = [], []
    for segment in _SEGMENT_RE.finditer(line):
        x = segment.start()
        if abs(x - competency_x) <= _COLUMN_SLACK:
            competency.append(segment.group())
        elif abs(x - indicator_x) <= _COLUMN_SLACK:
            indicator.append(segment.group())
        elif competency_x < x < indicator_x:
            return "", ""
    return " ".join(competency), " ".join(indicator)


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    competency_lines: list[str] = []
    indicator_lines: list[str] = []
    plain: list[str] = []
    columns = None  # отступы колонок последней страницы с таблицей
    for page in PdfReader(io.BytesIO(data)).pages:
        text = page.extract_text() or ""
        if not _CODE_RE.search(text):
            plain.append(text)  # раскладка медленная – строим ее только для страниц с кодами
            continue
        lines = [
            line
            for line in page.extract_text(extraction_mode="layout").splitlines()
            if not re.fullmatch(r"[\d\s]*", line)  # пустые строки и колонтитулы с номерами
        ]
        page_columns = _code_columns(lines, columns)
        if page_columns is None:
            plain.append(text)
            continue
        columns = page_columns
        for line in lines:
            competency, indicator = _table_cells(line, *columns)
            if competency:
                competency_lines.append(competency)
            if indicator:
                indicator_lines.append(indicator)
            if not competency and not indicator:
                # Строка вне колонок (заголовок, абзац, шапка таблицы) – граница: пустая
                # строка обрывает формулировку, и чужие слова к ней не приклеятся.
                competency_lines.append("")
                indicator_lines.append("")
    # Пустая строка между частями: формулировка не перетекает из одной в другую (parse_text).
    return "\n\n".join(["\n".join(competency_lines), "\n".join(indicator_lines), *plain])


# --- разбор текста ----------------------------------------------------------


def _better(current: str, candidate: str) -> str:
    """Из нескольких упоминаний кода оставляем самую содержательную формулировку."""
    if not candidate:
        return current
    if not current:
        return candidate
    return candidate if len(candidate) > len(current) else current


def parse_text(text: str) -> ParsedDocument:
    matches = list(_CODE_RE.finditer(text))
    competencies: dict[str, ParsedCompetency] = {}

    def competency(kind: str, num: str) -> ParsedCompetency:
        code = f"{kind}-{int(num)}"
        if code not in competencies:
            competencies[code] = ParsedCompetency(code=code, kind=models.CompetencyKind(kind))
        return competencies[code]

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # Формулировка не перетекает через пустую строку или в шапку следующей таблицы.
        tail = text[m.end() : end]
        description = clean_wording(_END_RE.split(tail, maxsplit=1)[0])
        g = m.groupdict()
        if g["a_kind"]:
            parent = competency(g["a_kind"], g["a_num"])
            ind_code = f"{parent.code}.{int(g['a_ind'])}"
        elif g["b_kind"]:
            parent = competency(g["b_kind"], g["b_num"])
            ind_code = f"{parent.code}.{int(g['b_ind'])}"
        else:
            parent = competency(g["c_kind"], g["c_num"])
            parent.description = _better(parent.description, description)
            continue
        parent.indicators[ind_code] = _better(parent.indicators.get(ind_code, ""), description)

    discipline = _DISCIPLINE_RE.search(text)
    return ParsedDocument(
        discipline_name=clean_wording(discipline.group("name")) if discipline else None,
        competencies=dict(sorted(competencies.items(), key=lambda kv: code_key(kv[0]))),
    )


# --- предпросмотр и сохранение ---------------------------------------------


def _existing(
    session: Session, direction_id: int, codes: list[str]
) -> dict[str, models.Competency]:
    rows = session.scalars(
        select(models.Competency)
        .where(models.Competency.direction_id == direction_id, models.Competency.code.in_(codes))
        .options(selectinload(models.Competency.indicators))
    )
    return {c.code: c for c in rows}


def _discipline(session: Session, direction_id: int, name: str) -> models.Discipline | None:
    return session.scalar(
        select(models.Discipline).where(
            models.Discipline.direction_id == direction_id, models.Discipline.name == name
        )
    )


def preview(
    session: Session, direction_id: int, filename: str, parsed: ParsedDocument
) -> schemas.ImportPreview:
    get_or_404(session, models.Direction, direction_id)
    existing = _existing(session, direction_id, list(parsed.competencies))
    items = []
    warnings = []
    for code, pc in parsed.competencies.items():
        current = existing.get(code)
        current_indicators = {i.code: i.description for i in current.indicators} if current else {}
        indicators = [
            schemas.ImportIndicator(
                code=ic,
                description=desc,
                exists=ic in current_indicators,
                changed=ic in current_indicators and differs(desc, current_indicators[ic]),
            )
            for ic, desc in sorted(pc.indicators.items(), key=lambda kv: int(kv[0].rsplit(".")[1]))
        ]
        if current is None:
            status = "new"
        elif any(not i.exists or i.changed for i in indicators) or differs(
            pc.description, current.description
        ):
            status = "update"
        else:
            status = "same"
        if current is None and not pc.description:
            warnings.append(f"{code}: формулировка не найдена – укажите её перед импортом")
        items.append(
            schemas.ImportCompetency(
                code=code,
                kind=pc.kind,
                description=pc.description,
                existing_description=current.description if current else None,
                status=status,
                indicators=indicators,
            )
        )
    discipline_exists = bool(
        parsed.discipline_name and _discipline(session, direction_id, parsed.discipline_name)
    )
    if not items:
        warnings.append("в файле не найдено кодов компетенций (УК-…, ОПК-…, ПК-…)")
    return schemas.ImportPreview(
        filename=filename,
        direction_id=direction_id,
        discipline_name=parsed.discipline_name,
        discipline_exists=discipline_exists,
        competencies=items,
        warnings=warnings,
    )


def apply(session: Session, data: schemas.ImportApply) -> schemas.ImportResult:
    """Создаёт в направлении недостающие компетенции и индикаторы, при желании обновляет
    формулировки, и привязывает компетенции к дисциплине направления. Ничего не удаляет."""
    get_or_404(session, models.Direction, data.direction_id)
    existing = _existing(session, data.direction_id, [c.code for c in data.competencies])
    result = schemas.ImportResult()
    touched: list[models.Competency] = []

    for item in data.competencies:
        competency = existing.get(item.code)
        if competency is None:
            if not item.description:
                raise DomainError(f"{item.code}: укажите формулировку компетенции")
            competency = models.Competency(
                direction_id=data.direction_id,
                code=item.code,
                kind=models.CompetencyKind(item.code.split("-")[0]),
                description=item.description,
            )
            session.add(competency)
            result.created_competencies += 1
        elif (
            data.overwrite_descriptions
            and item.description
            and item.description != competency.description
        ):
            competency.description = item.description
            result.updated_competencies += 1
        touched.append(competency)

        indicators = {i.code: i for i in competency.indicators}
        for ind in item.indicators:
            current = indicators.get(ind.code)
            if current is None:
                competency.indicators.append(
                    models.Indicator(code=ind.code, description=ind.description or ind.code)
                )
                result.created_indicators += 1
            elif (
                data.overwrite_descriptions
                and ind.description
                and ind.description != current.description
            ):
                current.description = ind.description
                result.updated_indicators += 1

    discipline = None
    if data.discipline_name:
        discipline = _discipline(session, data.direction_id, data.discipline_name)
        if discipline is None:
            discipline = models.Discipline(
                direction_id=data.direction_id, name=data.discipline_name
            )
            session.add(discipline)
            result.created_discipline = True
        linked = {c.code for c in discipline.competencies}
        for competency in touched:
            if competency.code not in linked:
                discipline.competencies.append(competency)
                result.linked_competencies += 1

    session.commit()
    if discipline is not None:
        result.discipline = schemas.DisciplineOut.model_validate(discipline)
    return result
