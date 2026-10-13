"""Эксплуатация: проверки работоспособности, id запроса, обработка ошибок, логи."""

import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import middleware
from app.db import get_session
from app.logging_setup import JsonFormatter, request_id_var
from app.main import VERSION, app


def test_health_reports_version(client: TestClient):
    assert client.get("/health").json() == {"status": "ok", "version": VERSION}


def test_ready_checks_database(client: TestClient):
    assert client.get("/ready").json()["status"] == "ok"

    class BrokenSession:
        def execute(self, *_):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    app.dependency_overrides[get_session] = lambda: BrokenSession()
    response = client.get("/ready")
    assert (response.status_code, response.json()["status"]) == (503, "unavailable")


def test_request_id(client: TestClient):
    generated = client.get("/health").headers["X-Request-ID"]
    assert len(generated) == 16
    # Id от обратного прокси сохраняется — по нему связываются логи прокси и приложения.
    assert (
        client.get("/health", headers={"X-Request-ID": "proxy-42"}).headers["X-Request-ID"]
        == "proxy-42"
    )


def test_unhandled_error_is_logged_not_leaked(caplog):
    broken = FastAPI()
    middleware.install(broken)

    @broken.get("/boom")
    def boom():
        raise RuntimeError("секретная деталь реализации")

    with caplog.at_level(logging.ERROR, logger="app.request"):
        response = TestClient(broken, raise_server_exceptions=False).get("/boom")
    request_id = response.headers["X-Request-ID"]
    assert response.status_code == 500
    assert request_id in response.json()["detail"]
    assert "секретная" not in response.text
    assert "секретная деталь реализации" in caplog.text  # стектрейс — в лог


def test_json_log_line():
    token = request_id_var.set("abc123")
    try:
        record = logging.LogRecord("app.request", logging.INFO, __file__, 1, "запрос", None, None)
        record.status, record.path, record.user = 201, "/directions", "admin"
        entry = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert entry["message"] == "запрос" and entry["request_id"] == "abc123"
    assert (entry["status"], entry["path"], entry["user"]) == (201, "/directions", "admin")
