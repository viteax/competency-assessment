#!/bin/sh
# Настройка копий базы вне сервера (docs/deploy.md, раздел 6). Запускать на сервере в копии
# прода от root:
#
#   cd /opt/competency && sh deploy/setup-offsite.sh yandex   # Yandex Object Storage
#   cd /opt/competency && sh deploy/setup-offsite.sh other    # другое хранилище rclone:
#                                                             # сервер по SFTP, Яндекс Диск, …
#
# Пишет deploy/rclone/rclone.conf: хранилище «store» и поверх него «offsite» – шифрование
# rclone crypt с паролем, который создается здесь же. Затем отправляет свежую копию, скачивает
# ее обратно и сравнивает, по желанию включает мониторинг (HEALTHCHECK_URL) и запускает сервис
# offsite. В конце печатает всю настройку: сохраните ее вне сервера – без нее копии из хранилища
# не расшифровать.
set -eu
cd "$(dirname "$0")/.."

compose="docker compose -f docker-compose.prod.yml"
conf=deploy/rclone/rclone.conf
rclone() { $compose run -T --rm --no-deps --entrypoint rclone offsite "$@"; }
fail() {
    echo "ошибка: $*" >&2
    exit 1
}
ask() {
    printf '%s' "$1" >&2
    read -r answer
    echo "$answer"
}
ask_secret() {
    printf '%s' "$1" >&2
    stty -echo 2>/dev/null || true
    read -r answer
    stty echo 2>/dev/null || true
    echo >&2
    echo "$answer"
}
trap 'stty echo 2>/dev/null || true' EXIT

case "${1:-}" in
yandex | other) ;;
*)
    echo "использование: sh deploy/setup-offsite.sh yandex | other" >&2
    exit 2
    ;;
esac
[ -f .env ] || fail "запускайте в копии прода, рядом с .env (обычно /opt/competency)"
[ ! -f "$conf" ] || fail "хранилище уже настроено ($conf). Чтобы настроить заново, удалите этот" \
    "файл – но копии, уже отправленные со старой настройкой, расшифровываются только ею."
umask 077
mkdir -p deploy/rclone

# Сначала все вопросы, потом настройка: ошибка в ответе не оставит полузаписанный файл.
if [ "$1" = yandex ]; then
    bucket=$(ask "Имя бакета: ")
    echo "$bucket" | grep -Eqx '[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]' ||
        fail "имя бакета – 3–63 строчные латинские буквы, цифры, точки и дефисы"
    key_id=$(ask "Идентификатор ключа: ")
    secret=$(ask_secret "Секретный ключ (не отображается): ")
    [ -n "$key_id" ] && [ -n "$secret" ] || fail "нужны идентификатор и секретный ключ"
    folder="$bucket/competency"
else
    folder=$(ask "Папка в хранилище для копий [competency-backups]: ")
    folder="${folder:-competency-backups}"
fi
hc=$(ask "Адрес проверки на healthchecks.io для сигналов о копиях (Enter – пропустить): ")
case "$hc" in "" | https://*) ;; *) fail "адрес проверки должен начинаться с https://" ;; esac

# Дальше при ошибке настройка откладывается в rclone.conf.failed: скрипт можно запустить снова.
abort() {
    [ ! -f "$conf" ] || mv "$conf" "$conf.failed"
    fail "$* Настройка отложена в $conf.failed, после исправления запустите скрипт снова."
}
if [ "$1" = yandex ]; then
    cat > "$conf" << EOF
[store]
type = s3
provider = Other
endpoint = storage.yandexcloud.net
region = ru-central1
access_key_id = $key_id
secret_access_key = $secret
no_check_bucket = true
EOF
else
    echo "Сейчас откроется мастер rclone (по-английски). Создайте хранилище: n (New remote)," \
        "имя store, дальше – тип и параметры хранилища; в конце q (Quit)." >&2
    $compose run --rm --no-deps --entrypoint rclone offsite config
    rclone listremotes < /dev/null | grep -qx 'store:' || abort "хранилище с именем store не создано."
fi

echo "→ ключ шифрования"
password=$(head -c 32 /dev/urandom | base64 | tr -d '\n/+=')
obscured=$(printf '%s\n' "$password" | rclone obscure -) || true
[ -n "$obscured" ] || abort "rclone не выдал ключ шифрования."
cat >> "$conf" << EOF

[offsite]
type = crypt
remote = store:$folder
password = $obscured
filename_encryption = off
directory_name_encryption = false
EOF

echo "→ свежая копия базы"
$compose exec -T backup sh /usr/local/bin/backup.sh < /dev/null || abort "копия базы не сделана."
echo "→ отправка в хранилище и проверка"
$compose run -T --rm --no-deps offsite --check < /dev/null ||
    abort "копия не дошла до хранилища – причина выше (ключи, имя бакета, права)."

if [ -n "$hc" ]; then
    { grep -v '^HEALTHCHECK_URL=' .env || true; } > .env.new
    echo "HEALTHCHECK_URL=$hc" >> .env.new
    cat .env.new > .env # права и владелец .env остаются прежними
    rm .env.new
fi
echo "→ сервис offsite"
$compose up -d --force-recreate offsite < /dev/null

cat << EOF

Готово: копии раз в час уходят в хранилище (свежая уже там), старые удаляются через
OFFSITE_KEEP_DAYS дней (по умолчанию 90).

Сохраните текст между линиями вне сервера – в менеджер паролей или зашифрованную заметку.
Без него копии из хранилища не расшифровать, например если сервер пропадет целиком.
------------------------------------------------------------------------------------------
$(cat "$conf")
------------------------------------------------------------------------------------------
EOF
