"""Middleware: id запроса и лог доступа, заголовки безопасности, журнал изменяющих действий."""

import logging
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app import models
from app.api.cookies import set_session_cookie
from app.config import settings
from app.db import get_session
from app.logging_setup import request_id_var

log = logging.getLogger("app.request")

# Интерфейс не подключает ничего стороннего, поэтому политика строгая. Inline-стили
# разрешены: интерфейс задаёт отступы атрибутом style, а исполняемого кода в них нет.
_CSP = (
    "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)
# Swagger UI грузит скрипты с CDN — на документацию CSP не распространяем.
_DOCS = ("/docs", "/redoc", "/openapi.json")
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Проверки работоспособности дёргаются каждые несколько секунд — в лог их не пишем.
_QUIET = {"/health", "/ready"}


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_and_audit(request: Request, call_next) -> Response:
        # Id запроса: берём от прокси, если он его выставил, иначе создаём свой.
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id[:64])
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Подробности — только в лог; пользователю — id, по которому их найти.
            log.exception("необработанная ошибка")
            response = JSONResponse(
                {"detail": f"внутренняя ошибка сервера, код запроса {request_id}"},
                status_code=500,
            )
        response.headers["X-Request-ID"] = request_id

        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "same-origin")
        if not request.url.path.startswith(_DOCS):
            headers.setdefault("Content-Security-Policy", _CSP)
        if settings.is_prod:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        if request.url.path.startswith("/ui"):
            # Браузер хранит файлы интерфейса, но перед использованием сверяет их с сервером
            # (по ETag): после обновления сразу подхватывается новая версия, без Ctrl+F5.
            headers.setdefault("Cache-Control", "no-cache")

        # Продлённую сессию готовит зависимость get_current_user.
        renewed = getattr(request.state, "renewed_session", None)
        if renewed and response.status_code < 400:
            set_session_cookie(response, renewed)

        # (id, логин) кладёт в request.state зависимость get_current_user.
        actor = getattr(request.state, "actor", None)
        if actor is not None and request.method not in _SAFE_METHODS:
            await run_in_threadpool(_record, app, actor, request, response.status_code)

        if request.url.path not in _QUIET:
            log.info(
                "запрос",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    "user": actor[1] if actor else None,
                    "ip": request.client.host if request.client else None,
                },
            )
        request_id_var.reset(token)
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
