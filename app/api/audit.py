from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app import models, schemas
from app.api.deps import SessionDep, require_admin

router = APIRouter(tags=["Журнал"], dependencies=[Depends(require_admin)])


@router.get("/audit", response_model=list[schemas.AuditEntryOut])
def list_audit(
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    username: str | None = None,
):
    """Изменяющие действия пользователей, новые сверху."""
    stmt = select(models.AuditEntry).order_by(models.AuditEntry.id.desc())
    if username:
        stmt = stmt.where(models.AuditEntry.username == username)
    return session.scalars(stmt.limit(limit).offset(offset)).all()
