#!/bin/sh
# Обновление на сервере по команде из GitHub Actions (.github/workflows/ci.yml).
#
# Запускается только как принудительная команда SSH-ключа деплоя в authorized_keys:
#   restrict,command="/opt/competency/deploy/remote-deploy.sh" ssh-ed25519 AAAA... deploy
# Ключ не дает shell: что бы ни прислал клиент, выполнится этот скрипт, а присланная строка
# придет в SSH_ORIGINAL_COMMAND и разбирается ниже. Допустимы ровно две команды:
#   demo             – демо-стенд из свежего main
#   prod 1.2.3       – прод на образ ghcr.io/viteax/competency-assessment:1.2.3
set -eu

PROD_DIR=/opt/competency
DEMO_DIR=/opt/competency-demo
IMAGE=ghcr.io/viteax/competency-assessment

set -f # без подстановки имен файлов: строка пришла снаружи
# shellcheck disable=SC2086 # разбиваем строку на слова намеренно
set -- ${SSH_ORIGINAL_COMMAND:-}
target="${1:-}"
version="${2:-}"

case "$target" in
demo)
    cd "$DEMO_DIR"
    git fetch -q origin main
    git reset -q --hard origin/main
    docker compose -f docker-compose.demo.yml up -d --build --remove-orphans
    echo "demo: $(git rev-parse --short HEAD)"
    ;;
prod)
    # Только версия вида 1.2.3: строка приходит снаружи и попадает в команды ниже.
    echo "$version" | grep -Eqx '[0-9]+\.[0-9]+\.[0-9]+' || {
        echo "ожидается версия вида 1.2.3, получено: '$version'" >&2
        exit 2
    }
    cd "$PROD_DIR"
    compose="docker compose -f docker-compose.prod.yml"

    echo "→ резервная копия перед обновлением"
    $compose exec -T backup sh /usr/local/bin/backup.sh

    echo "→ код и конфигурация версии v$version"
    git fetch -q --tags origin
    git checkout -q "v$version"

    echo "→ образ $IMAGE:$version"
    if grep -q '^APP_IMAGE=' .env; then
        sed -i "s|^APP_IMAGE=.*|APP_IMAGE=$IMAGE:$version|" .env
    else
        echo "APP_IMAGE=$IMAGE:$version" >> .env
    fi
    $compose pull api
    $compose up -d --remove-orphans # миграции применятся при старте api
    echo "prod: v$version"
    ;;
*)
    echo "использование: demo | prod <версия>" >&2
    exit 2
    ;;
esac
