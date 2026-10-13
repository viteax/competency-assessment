from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import models
from app.db import get_session
from app.errors import Forbidden, Unauthorized
from app.security import decode_access_token

SessionDep = Annotated[Session, Depends(get_session)]

# Веб-интерфейс хранит токен в httpOnly-cookie (недоступна JavaScript), внешние клиенты
# и Swagger передают его в заголовке Authorization: Bearer.
SESSION_COOKIE = "session"
CSRF_HEADER = "X-Requested-With"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def client_ip(request: Request) -> str:
    # За обратным прокси uvicorn подставляет реальный адрес (--proxy-headers).
    return request.client.host if request.client else "unknown"


def get_current_user(
    request: Request,
    session: SessionDep,
    bearer: Annotated[str | None, Depends(oauth2_scheme)],
) -> models.User:
    token = bearer or request.cookies.get(SESSION_COOKIE)
    decoded = decode_access_token(token) if token else None
    user = session.get(models.User, decoded[0]) if decoded else None
    if user is None or user.token_version != decoded[1]:
        raise Unauthorized("войдите в систему", headers={"WWW-Authenticate": "Bearer"})
    # Cookie браузер подставляет сам, поэтому изменяющие запросы с ней должны нести заголовок,
    # который чужой сайт выставить не может (защита от CSRF вдобавок к SameSite=Strict).
    if not bearer and request.method not in _SAFE_METHODS and CSRF_HEADER not in request.headers:
        raise Forbidden("запрос отклонён: нет заголовка X-Requested-With")
    # Для журнала действий — только простые значения: сессия БД к тому времени закрыта.
    request.state.actor = (user.id, user.username)
    return user


CurrentUser = Annotated[models.User, Depends(get_current_user)]


def get_active_user(user: CurrentUser) -> models.User:
    """Пользователь, которому не нужно сначала сменить выданный пароль."""
    if user.must_change_password:
        raise Forbidden("сначала смените выданный пароль")
    return user


ActiveUser = Annotated[models.User, Depends(get_active_user)]


def require_admin(user: ActiveUser) -> models.User:
    if user.role != models.Role.ADMIN:
        raise Forbidden("нужны права администратора")
    return user


def require_student(user: ActiveUser) -> models.Student:
    if user.role != models.Role.STUDENT or user.student is None:
        raise Forbidden("доступно только студентам")
    return user.student


AdminUser = Annotated[models.User, Depends(require_admin)]
CurrentStudent = Annotated[models.Student, Depends(require_student)]
