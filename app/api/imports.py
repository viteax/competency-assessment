"""Импорт из файлов: компетенции из ОПОП / РПД и студенты из выгрузки СДО.
Везде сначала предпросмотр, затем сохранение."""

import json

from fastapi import APIRouter, Depends, Form, UploadFile

from app import schemas
from app.api.deps import SessionDep, require_admin
from app.errors import DomainError
from app.services import (
    competency_import,
    files,
    plan_import,
    student_columns,
    student_import,
)

router = APIRouter(prefix="/import", tags=["Импорт"], dependencies=[Depends(require_admin)])


async def _read(file: UploadFile) -> tuple[str, bytes]:
    # Читаем на байт больше лимита, чтобы files.file_kind заметил слишком большой файл.
    return file.filename or "", await file.read(files.MAX_FILE_SIZE + 1)


@router.post("/preview", response_model=schemas.ImportPreview)
async def preview(file: UploadFile, session: SessionDep, direction_id: int = Form()):
    """Разбирает файл (.docx, .xlsx, .pdf, .txt) и показывает, что будет создано или обновлено
    в направлении direction_id. В БД ничего не пишет."""
    filename, data = await _read(file)
    text = competency_import.extract_text(filename, data)
    parsed = competency_import.parse_text(text)
    return competency_import.preview(session, direction_id, filename, parsed)


@router.post("/apply", response_model=schemas.ImportResult)
def apply(data: schemas.ImportApply, session: SessionDep):
    """Сохраняет проверенный администратором результат предпросмотра."""
    return competency_import.apply(session, data)


@router.post("/plan/preview", response_model=schemas.PlanPreview)
async def preview_plan(
    file: UploadFile, session: SessionDep, merge_into: int | None = Form(default=None)
):
    """Учебный план из «Планов» (.xlsx): что будет создано или дополнено – направление,
    компетенции, дисциплины с семестрами и статусом, профстандарты, ОТФ, ТФ и их связи с
    компетенциями. В БД ничего не пишет."""
    filename, data = await _read(file)
    files.file_kind(filename, data, (".xlsx",))
    return plan_import.preview(session, filename, plan_import.parse(data), merge_into)


@router.post("/plan/apply", response_model=schemas.PlanResult)
async def apply_plan(
    file: UploadFile,
    session: SessionDep,
    overwrite_descriptions: bool = Form(default=False),
    merge_into: int | None = Form(default=None),
    create_new: bool = Form(default=False),
):
    """Загружает тот же файл: создает недостающее и дополняет существующее, ничего не удаляет."""
    filename, data = await _read(file)
    files.file_kind(filename, data, (".xlsx",))
    return plan_import.apply(
        session, plan_import.parse(data), overwrite_descriptions, merge_into, create_new
    )


@router.post("/students/preview", response_model=schemas.StudentImportPreview)
async def preview_students(
    file: UploadFile, session: SessionDep, mapping: str | None = Form(default=None)
):
    """Разбирает CSV/XLSX со списком студентов. Колонки определяются по заголовкам;
    `mapping` (JSON `{"full_name": 0, "group": 3, ...}`) задаёт их вручную."""
    filename, data = await _read(file)
    table = student_columns.read_table(filename, data)
    manual = None
    if mapping:
        try:
            manual = {
                k: (int(v) if v is not None else None)
                for k, v in json.loads(mapping).items()
                if k in student_columns.FIELDS
            }
        except (ValueError, TypeError, AttributeError) as exc:
            raise DomainError("mapping должен быть JSON-объектом с номерами колонок") from exc
    return student_import.preview(session, filename, table, manual)


@router.post("/students/apply", response_model=schemas.StudentImportResult)
def apply_students(data: schemas.StudentImportApply, session: SessionDep):
    """Создаёт и обновляет студентов; при `create_accounts` выдаёт логины и пароли новым."""
    return student_import.apply(session, data)
