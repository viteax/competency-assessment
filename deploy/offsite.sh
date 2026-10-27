#!/bin/sh
# Копии базы вне сервера и сигналы мониторингу, что копии делаются.
#
#   offsite.sh           – проход раз в час (так запускает compose, сервис offsite)
#   offsite.sh --once    – один проход сейчас
#   offsite.sh --check   – отправить последнюю копию, скачать ее обратно и сравнить
#
# Проход: если в /backups нет копии моложе 26 часов – сигнал о сбое. Иначе новые копии уходят
# в хранилище «offsite:» (rclone, шифруются до отправки), там удаляются копии старше
# OFFSITE_KEEP_DAYS дней, и мониторинг получает сигнал «все в порядке». Если отправить не
# удалось, сигнала нет: мониторинг напишет, когда сигналы перестанут приходить, а сбой сети на
# час-другой тревоги не поднимет.
#
# Хранилище настраивает deploy/setup-offsite.sh (rclone.conf), мониторинг – HEALTHCHECK_URL
# (healthchecks.io); что не настроено, пропускается. Подробно – docs/deploy.md, раздел 6.
set -u

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP_DAYS="${OFFSITE_KEEP_DAYS:-90}"
STATE="${OFFSITE_STATE:-/tmp/offsite-sent}" # отметка времени последней удачной отправки

log() { echo "$(date -Iseconds) $*"; }

# Сигнал мониторингу: signal "" "текст" – все в порядке, signal /fail "текст" – сбой.
signal() {
    [ -n "${HEALTHCHECK_URL:-}" ] || return 0
    wget -q -O /dev/null -T 30 --post-data "$2" "$HEALTHCHECK_URL$1" || log "мониторинг недоступен"
}

configured() { rclone listremotes 2>/dev/null | grep -qx 'offsite:'; }

newest() { ls -t "$BACKUP_DIR"/competency-*.dump 2>/dev/null | head -n 1; }

run_once() {
    latest=$(newest)
    if [ -z "$latest" ] || [ -z "$(find "$latest" -mmin -1560)" ]; then
        log "нет копии базы моложе 26 часов (последняя: ${latest:-нет})"
        signal /fail "Нет копии базы моложе 26 часов (последняя: ${latest:-нет}). Смотрите:
docker compose -f docker-compose.prod.yml logs backup"
        return 1
    fi
    name=${latest##*/}
    if ! configured; then
        signal "" "$name – только на сервере: хранилище не настроено"
        return 0
    fi
    if [ ! -f "$STATE" ] || [ -n "$(find "$BACKUP_DIR" -name 'competency-*.dump' -newer "$STATE")" ]; then
        touch "$STATE.next"
        if ! rclone copy "$BACKUP_DIR" offsite: --include 'competency-*.dump' ||
            ! rclone delete offsite: --include 'competency-*.dump' --min-age "${KEEP_DAYS}d"; then
            log "не удалось отправить копии в хранилище, повтор через час"
            return 1
        fi
        mv "$STATE.next" "$STATE"
        log "в хранилище: $name"
    fi
    signal "" "$name – на сервере и в хранилище"
}

verify() {
    latest=$(newest)
    [ -n "$latest" ] || { echo "в $BACKUP_DIR нет копий" >&2; return 1; }
    configured || { echo "хранилище не настроено: deploy/setup-offsite.sh" >&2; return 1; }
    name=${latest##*/}
    rclone copy "$latest" offsite: || return 1
    here=$(sha256sum < "$latest" | cut -d' ' -f1)
    there=$(rclone cat "offsite:$name" | sha256sum | cut -d' ' -f1)
    if [ "$here" != "$there" ]; then
        echo "копия $name из хранилища не совпадает с копией на сервере" >&2
        return 1
    fi
    echo "проверка пройдена: $name отправлена, скачана из хранилища и совпала с копией на сервере"
}

case "${1:-}" in
--once) run_once ;;
--check) verify ;;
"")
    storage="не настроено" monitoring="не настроен"
    configured && storage="offsite:, хранить $KEEP_DAYS дней"
    [ -z "${HEALTHCHECK_URL:-}" ] || monitoring="включен"
    log "копии вне сервера: $storage; мониторинг: $monitoring"
    while true; do
        run_once || true
        sleep 3600
    done
    ;;
*)
    echo "использование: offsite.sh [--once | --check]" >&2
    exit 2
    ;;
esac
