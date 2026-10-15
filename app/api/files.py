"""Ответы-файлы для скачивания."""

from urllib.parse import quote

from fastapi import Response

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def attachment(content: bytes, filename: str, media_type: str) -> Response:
    """Файл с русским именем (RFC 5987: filename*=UTF-8'')."""
    return Response(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
