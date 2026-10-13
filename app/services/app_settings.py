"""Настройки, которые администратор меняет в интерфейсе. Пока не заданы в базе, действуют
значения из окружения (app.config)."""

from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.errors import DomainError

MASTERY_THRESHOLD = "mastery_threshold"


def mastery_threshold(session: Session) -> float:
    row = session.get(models.AppSetting, MASTERY_THRESHOLD)
    return float(row.value) if row else settings.mastery_threshold


def set_mastery_threshold(session: Session, value: float) -> float:
    if not 0 < value <= 1:
        raise DomainError("порог — доля верных ответов от 0 до 1, например 0.6")
    row = session.get(models.AppSetting, MASTERY_THRESHOLD)
    if row is None:
        session.add(models.AppSetting(key=MASTERY_THRESHOLD, value=str(value)))
    else:
        row.value = str(value)
    session.commit()
    return value
