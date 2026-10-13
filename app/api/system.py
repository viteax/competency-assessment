"""Настройки системы (администратор)."""

from fastapi import APIRouter, Depends

from app import schemas
from app.api.deps import SessionDep, require_admin
from app.services import app_settings

router = APIRouter(tags=["Настройки"], dependencies=[Depends(require_admin)])


@router.get("/settings", response_model=schemas.SystemSettings)
def get_settings(session: SessionDep):
    return schemas.SystemSettings(mastery_threshold=app_settings.mastery_threshold(session))


@router.put("/settings", response_model=schemas.SystemSettings)
def update_settings(data: schemas.SystemSettings, session: SessionDep):
    """Порог влияет на все отчёты сразу: результаты пересчитываются при каждом запросе."""
    return schemas.SystemSettings(
        mastery_threshold=app_settings.set_mastery_threshold(session, data.mastery_threshold)
    )
