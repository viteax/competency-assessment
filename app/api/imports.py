"""Импорт из файлов: компетенции из ОПОП / РПД и студенты из выгрузки СДО.
Везде сначала предпросмотр, затем сохранение."""

import json

from fastapi import APIRouter, Depends, Form, UploadFile

from app import schemas
from app.api.deps import SessionDep, require_admin
from app.errors import DomainError
from app.services import importer, student_import

router = APIRouter(prefix="/import", tags=["Импорт"], dependencies=[Depends(require_admin)])


@router.post("/preview", response_model=schemas.ImportPreview)
async def preview(file: UploadFile, session: SessionDep):
    """Разбирает файл (.docx, .xlsx, .pdf, .txt) и показывает, что будет создано или обновлено.
    В БД ничего не пишет."""
    data = await file.read(importer.MAX_FILE_SIZE + 1)
    text = importer.extract_text(file.filename or "", data)
    return importer.preview(session, file.filename or "", importer.parse_text(text))


@router.post("/apply", response_model=schemas.ImportResult)
def apply(data: schemas.ImportApply, session: SessionDep):
    """Сохраняет проверенный администратором результат предпросмотра."""
    return importer.apply(session, data)


@router.post("/students/preview", response_model=schemas.StudentImportPreview)
async def preview_students(
    file: UploadFile, session: SessionDep, mapping: str | None = Form(default=None)
):
    """Разбирает CSV/XLSX со списком студентов. Колонки определяются по заголовкам;
    `mapping` (JSON `{"full_name": 0, "group": 3, ...}`) задаёт их вручную."""
    data = await file.read(importer.MAX_FILE_SIZE + 1)
    table = student_import.read_table(file.filename or "", data)
    manual = None
    if mapping:
        try:
            manual = {
                k: (int(v) if v is not None else None)
                for k, v in json.loads(mapping).items()
                if k in student_import.FIELDS
            }
        except (ValueError, TypeError, AttributeError) as exc:
            raise DomainError("mapping должен быть JSON-объектом с номерами колонок") from exc
    return student_import.preview(session, file.filename or "", table, manual)


@router.post("/students/apply", response_model=schemas.StudentImportResult)
def apply_students(data: schemas.StudentImportApply, session: SessionDep):
    """Создаёт и обновляет студентов; при `create_accounts` выдаёт логины и пароли новым."""
    return student_import.apply(session, data)
