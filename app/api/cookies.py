"""Cookie веб-интерфейса: сессия и отметка доверенного устройства."""

from fastapi import Response

from app.config import settings
from app.security import DEVICE_TOKEN_DAYS

SESSION_COOKIE = "session"
DEVICE_COOKIE = "device"


def set_session_cookie(response: Response, token: str) -> None:
    # Без max_age: cookie живёт до закрытия браузера. Сам токен истекает после
    # session_idle_minutes без действий – на общем компьютере сессия не останется надолго.
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, secure=settings.is_prod, samesite="strict"
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, secure=settings.is_prod, samesite="strict"
    )


def set_device_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        DEVICE_COOKIE,
        token,
        max_age=DEVICE_TOKEN_DAYS * 24 * 3600,
        path="/auth",  # нужна только при входе
        httponly=True,
        secure=settings.is_prod,
        samesite="strict",
    )
