import base64

from fastapi import APIRouter, Depends

from app import schemas
from app.api.deps import get_active_user
from app.api.files import DOCX, attachment
from app.errors import DomainError
from app.services import word_export

router = APIRouter(prefix="/charts", tags=["Отчёты"], dependencies=[Depends(get_active_user)])

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@router.post("/docx")
def chart_docx(data: schemas.ChartExport):
    """«Роза ветров» в Word: картинку рисует браузер, сервер собирает документ с подписью."""
    try:
        image = base64.b64decode(data.image.removeprefix("data:image/png;base64,"), validate=True)
    except ValueError as e:  # не base64 или не ASCII
        raise DomainError("картинка должна быть PNG в base64") from e
    if not image.startswith(PNG_SIGNATURE):
        raise DomainError("картинка должна быть PNG в base64")
    content = word_export.chart_document(data.title, image, data.legend, data.rows)
    return attachment(content, f"{data.title}.docx", DOCX)
