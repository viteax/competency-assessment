#!/bin/sh
# Разовая настройка сервера для автоматического обновления (docs/deploy.md, раздел 9).
# Запускать от root в копии прода, когда прод уже работает:
#
#   sudo sh deploy/setup-cd.sh demo.example.ru [внешний IP сервера]
#
# Поднимает демо-стенд рядом с продом и дает ему адрес в Caddy, создает ключ деплоя,
# который может только запускать deploy/remote-deploy.sh, и печатает значения для GitHub.
# Повторный запуск безопасен: демо обновится, старый ключ деплоя заменится новым.
set -eu

[ "$(id -u)" = 0 ] || { echo "запустите от root: sudo sh $0 <адрес демо>" >&2; exit 2; }
demo_address="${1:-}"
echo "$demo_address" | grep -Eqx '[A-Za-z0-9.-]+' || {
    echo "укажите адрес демо-стенда, например demo.example.ru" >&2
    exit 2
}
host="${2:-$(hostname -I | awk '{print $1}')}"

PROD_DIR=$(cd "$(dirname "$0")/.." && pwd)
DEMO_DIR="$PROD_DIR-demo"
cd "$PROD_DIR"
compose="docker compose -f docker-compose.prod.yml"
$compose ps --status running --services | grep -qx caddy || {
    echo "прод не запущен: сначала разделы 2–3 docs/deploy.md" >&2
    exit 1
}
sshd -T 2>/dev/null | grep -qx 'permitrootlogin no' && {
    echo "sshd запрещает вход root (PermitRootLogin no): разрешите prohibit-password" >&2
    exit 1
}

echo "→ демо-стенд в $DEMO_DIR"
[ -d "$DEMO_DIR/.git" ] || git clone -q "$(git remote get-url origin)" "$DEMO_DIR"
SSH_ORIGINAL_COMMAND=demo sh deploy/remote-deploy.sh

echo "→ адрес демо $demo_address"
printf '%s {\n\treverse_proxy demo-api:8000\n}\n' "$demo_address" > deploy/sites/demo.caddy
# Перезапуск, а не reload: Caddyfile подключен файлом, и после git pull контейнер видит старый.
$compose restart caddy

echo "→ ключ деплоя"
keys=$(mktemp -d)
trap 'rm -rf "$keys"' EXIT
ssh-keygen -q -t ed25519 -N "" -C competency-deploy -f "$keys/key"
install -m 700 -d /root/.ssh
touch /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
sed -i '/ competency-deploy$/d' /root/.ssh/authorized_keys
echo "restrict,command=\"$PROD_DIR/deploy/remote-deploy.sh\" $(cat "$keys/key.pub")" \
    >> /root/.ssh/authorized_keys

cat <<INFO

Готово. Внесите в GitHub: Settings → Secrets and variables → Actions.

Secret DEPLOY_SSH_KEY (приватный ключ одной строкой base64 – скопируйте ее целиком):
$(base64 -w0 "$keys/key")
Отпечаток (для сверки с логом деплоя): $(ssh-keygen -l -f "$keys/key" | cut -d' ' -f2)

Secret DEPLOY_KNOWN_HOSTS:
$host $(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)

Variable DEPLOY_HOST: $host
Variable DEMO_URL:    https://$demo_address
Variable PROD_URL:    https://<адрес прода из SITE_ADDRESS>

Если сервер за NAT и $host – не тот адрес, по которому вы заходите по SSH,
запустите скрипт снова, указав внешний IP вторым аргументом.
Приватный ключ больше нигде не хранится: после копирования очистите экран (clear).
INFO
