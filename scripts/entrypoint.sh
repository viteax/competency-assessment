#!/bin/sh
# Точка входа контейнера: миграции, затем сервер.
set -eu

alembic upgrade head

# --proxy-headers: реальный IP клиента и схема https – из заголовков обратного прокси (Caddy).
# Доверяем им от любого адреса, потому что порт приложения наружу не открыт: в него может
# обратиться только прокси из той же docker-сети. Если открываете порт – сузьте FORWARDED_ALLOW_IPS.
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${WEB_CONCURRENCY:-2}" \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
    --no-server-header
