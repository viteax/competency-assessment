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
# (healthchecks.io) и/или сообщения во VK (NOTIFY_VK_TOKEN – токен сообщества с доступом к
# сообщениям, NOTIFY_VK_USER_ID – кому писать). healthchecks.io не принимает запросы с российских
# IP, поэтому на таком сервере нужен VK: сбой – сразу (не чаще раза в 6 часов), «все в порядке» –
# раз в день; нет утреннего сообщения – значит, сломалось само наблюдение. Что не настроено,
# пропускается. Подробно – docs/deploy.md, раздел 6.
set -u

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP_DAYS="${OFFSITE_KEEP_DAYS:-90}"
STATE="${OFFSITE_STATE:-/tmp/offsite-sent}" # отметка времени последней удачной отправки

log() { echo "$(date -Iseconds) $*"; }

# Сообщение во VK от имени сообщества: vk "текст".
vk() {
    # Тело формы: экранируем то, что ломает разбор (%, &, +, =), переводы строк – %0A.
    text=$(printf '%s' "$1" | awk 'BEGIN { ORS = "%0A" } { gsub(/%/, "%25"); gsub(/&/, "%26"); gsub(/\+/, "%2B"); gsub(/=/, "%3D"); print }')
    answer=$(wget -q -O - -T 30 --post-data "access_token=$NOTIFY_VK_TOKEN&user_id=$NOTIFY_VK_USER_ID&random_id=$(date +%s)&v=5.199&message=$text" \
        https://api.vk.com/method/messages.send) || { log "VK недоступен"; return 1; }
    case "$answer" in *'"error"'*) log "VK отказал: $answer"; return 1 ;; esac
}

# Сигнал мониторингу: signal "" "текст" – все в порядке, signal /fail "текст" – сбой.
signal() {
    if [ -n "${HEALTHCHECK_URL:-}" ]; then
        wget -q -O /dev/null -T 30 --post-data "$2" "$HEALTHCHECK_URL$1" || log "мониторинг недоступен"
    fi
    [ -n "${NOTIFY_VK_TOKEN:-}" ] && [ -n "${NOTIFY_VK_USER_ID:-}" ] || return 0
    if [ "$1" = /fail ]; then
        [ -z "$(find "$STATE.vk-fail" -mmin -360 2>/dev/null)" ] || return 0
        vk "Сбой копий базы competency: $2" && touch "$STATE.vk-fail"
    else
        rm -f "$STATE.vk-fail" # после восстановления о новом сбое сообщим сразу
        [ "$(cat "$STATE.vk-ok" 2>/dev/null)" != "$(date +%F)" ] || return 0
        vk "Копии базы competency в порядке: $2" && date +%F > "$STATE.vk-ok"
    fi
    return 0 # сбой уведомления – только в логе, на результат прохода не влияет
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
    storage="не настроено" monitoring=""
    configured && storage="offsite:, хранить $KEEP_DAYS дней"
    [ -z "${HEALTHCHECK_URL:-}" ] || monitoring="healthchecks.io "
    [ -z "${NOTIFY_VK_TOKEN:-}" ] || monitoring="${monitoring}VK"
    log "копии вне сервера: $storage; мониторинг: ${monitoring:-не настроен}"
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
