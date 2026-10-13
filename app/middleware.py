"""Заголовки безопасности и журнал изменяющих действий."""

from fastapi import FastAPI, Request, Response
from starlette.concurrency import run_in_threadpool

from app import models
from app.api.cookies import set_session_cookie
from app.config import settings
from app.db import get_session

# Интерфейс не подключает ничего стороннего, поэтому политика строгая. Inline-стили
# разрешены: интерфейс задаёт отступы атрибутом style, а исполняемого кода в них нет.
_CSP = (
    "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)
# Swagger UI грузит скрипты с CDN — на документацию CSP не распространяем.
_DOCS = ("/docs", "/redoc", "/openapi.json")
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_and_audit(request: Request, call_next) -> Response:
        response = await call_next(request)

        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "same-origin")
        if not request.url.path.startswith(_DOCS):
            headers.setdefault("Content-Security-Policy", _CSP)
        if settings.is_prod:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000")

        # Продлённую сессию готовит зависимость get_current_user.
        renewed = getattr(request.state, "renewed_session", None)
        if renewed and response.status_code < 400:
            set_session_cookie(response, renewed)

        # (id, логин) кладёт в request.state зависимость get_current_user.
        actor = getattr(request.state, "actor", None)
        if actor is not None and request.method not in _SAFE_METHODS:
            await run_in_threadpool(_record, app, actor, request, response.status_code)
        return response


def _record(app: FastAPI, actor: tuple[int, str], request: Request, status_code: int) -> None:
    # Сессию берём через ту же зависимость, что и обработчики, — в тестах она подменена.
    sessions = app.dependency_overrides.get(get_session, get_session)()
    session = next(sessions)
    try:
        session.add(
            models.AuditEntry(
                user_id=actor[0],
                username=actor[1],
                method=request.method,
                path=request.url.path[:255],
                status_code=status_code,
                ip=request.client.host if request.client else "unknown",
            )
        )
        session.commit()
    finally:
        sessions.close()
