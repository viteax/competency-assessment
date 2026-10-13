"""Логи: в prod — JSON по строке на событие (удобно для docker logs, Loki, ELK), в dev — текст.

Каждая строка внутри запроса несёт его request_id — по нему находится вся история запроса,
а пользователь видит этот же id в ответе с ошибкой и может назвать его администратору.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

from app.config import settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Поля, которые middleware передаёт через extra= и которые нужно вывести.
_EXTRA = ("method", "path", "status", "duration_ms", "user", "ip")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if request_id := request_id_var.get():
            entry["request_id"] = request_id
        entry.update({k: getattr(record, k) for k in _EXTRA if hasattr(record, k)})
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        extra = " ".join(f"{k}={getattr(record, k)}" for k in _EXTRA if hasattr(record, k))
        request_id = request_id_var.get()
        line = f"{record.levelname:<7} {record.name}: {record.getMessage()}"
        line += f" {extra}" if extra else ""
        line += f" [{request_id}]" if request_id else ""
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.is_prod else TextFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    # Запросы логирует наш middleware (с пользователем и request_id) — встроенный лог доступа
    # uvicorn дублировал бы его без этих полей.
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
