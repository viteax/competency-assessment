"""Импорт компетенций из файлов ОПОП / РПД: предпросмотр, затем сохранение."""

from fastapi import APIRouter, Depends, UploadFile

from app import schemas
from app.api.deps import SessionDep, require_admin
from app.services import importer

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
