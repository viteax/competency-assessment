from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api import auth, competencies, me, questions, reports, standards, study, testing
from app.errors import DomainError

app = FastAPI(
    title="Competency Assessment",
    description="Тестирование студентов по компетенциям ФГОС с привязкой к профстандарту",
    version="0.1.0",
)

for module in (auth, me, study, competencies, standards, questions, testing, reports):
    app.include_router(module.router)


@app.exception_handler(DomainError)
def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(IntegrityError)
def handle_integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        {"detail": "запись нарушает ограничение уникальности или ссылочной целостности"},
        status_code=409,
    )


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
