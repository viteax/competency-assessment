from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app import middleware
from app.api import (
    audit,
    auth,
    competencies,
    imports,
    me,
    questions,
    reports,
    standards,
    study,
    testing,
)
from app.config import settings
from app.db import SessionLocal
from app.errors import DomainError
from app.services import auth as auth_service


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.is_prod:
        with SessionLocal() as session:
            exposed = auth_service.demo_passwords_in_use(session)
        if exposed:
            raise RuntimeError(
                "в ENVIRONMENT=prod у демо-учёток публичные пароли: "
                f"{', '.join(exposed)} — удалите их или смените пароли"
            )
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Competency Assessment",
    description="Тестирование студентов по компетенциям ФГОС с привязкой к профстандарту",
    version="0.1.0",
)

for module in (
    auth,
    me,
    study,
    competencies,
    standards,
    questions,
    testing,
    reports,
    imports,
    audit,
):
    app.include_router(module.router)

middleware.install(app)


@app.exception_handler(DomainError)
def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(IntegrityError)
def handle_integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        {"detail": "запись нарушает ограничение уникальности или ссылочной целостности"},
        status_code=409,
    )


app.mount("/ui", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="ui")


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse("/ui/")


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
