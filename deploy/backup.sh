#!/bin/sh
# Резервные копии PostgreSQL.
#
#   backup.sh            – сделать копию сейчас
#   backup.sh --daemon   – делать копию каждый день в BACKUP_TIME (так запускает compose)
#
# Копии: /backups/competency-ГГГГ-ММ-ДД_ЧЧММ.dump (формат pg_dump -Fc, сжатый). Хранятся
# BACKUP_KEEP_DAYS дней. Подключение – через стандартные переменные PGHOST, PGUSER, PGPASSWORD,
# PGDATABASE. Восстановление – deploy/restore.sh.
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"

backup_now() {
    stamp=$(date +%Y-%m-%d_%H%M)
    target="$BACKUP_DIR/competency-$stamp.dump"
    # Пишем во временный файл: оборванная копия не должна выглядеть как настоящая.
    pg_dump --format=custom --no-owner --file="$target.partial"
    pg_restore --list "$target.partial" > /dev/null # копия читается
    mv "$target.partial" "$target"
    find "$BACKUP_DIR" -name 'competency-*.dump' -mtime +"$KEEP_DAYS" -delete
    echo "$(date -Iseconds) backup ok: $target ($(du -h "$target" | cut -f1))"
}

if [ "${1:-}" != "--daemon" ]; then
    backup_now
    exit 0
fi

echo "$(date -Iseconds) backups daily at ${BACKUP_TIME:-03:30}, keep $KEEP_DAYS days, dir $BACKUP_DIR"
while true; do
    if [ "$(date +%H:%M)" = "${BACKUP_TIME:-03:30}" ]; then
        backup_now || echo "$(date -Iseconds) backup FAILED" >&2
        sleep 61 # не повторить в ту же минуту
    fi
    sleep 20
done
