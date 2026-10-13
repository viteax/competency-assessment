#!/bin/sh
# Восстановление базы из резервной копии. Запускать на сервере из папки проекта:
#
#   deploy/restore.sh backups/competency-2026-10-13_0330.dump
#
# Останавливает приложение, пересоздаёт базу из копии и запускает приложение снова.
# Текущие данные будут заменены — перед этим скрипт делает свежую копию на всякий случай.
set -eu

DUMP="${1:?укажите файл копии, например backups/competency-2026-10-13_0330.dump}"
[ -f "$DUMP" ] || { echo "файл $DUMP не найден" >&2; exit 1; }
COMPOSE="docker compose -f docker-compose.prod.yml"

printf "База будет заменена копией %s. Продолжить? [y/N] " "$DUMP"
read -r answer
[ "$answer" = "y" ] || { echo "отменено"; exit 1; }

echo "→ копия текущего состояния"
$COMPOSE exec -T backup sh /usr/local/bin/backup.sh

echo "→ остановка приложения"
$COMPOSE stop api

echo "→ восстановление"
$COMPOSE exec -T db dropdb -U competency --if-exists competency
$COMPOSE exec -T db createdb -U competency competency
$COMPOSE exec -T db pg_restore -U competency -d competency --no-owner < "$DUMP"

echo "→ запуск приложения (миграции применятся автоматически)"
$COMPOSE start api
echo "готово"
