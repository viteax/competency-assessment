#!/bin/sh
# Обновление на сервере по команде из GitHub Actions (.github/workflows/ci.yml).
#
# Запускается только как принудительная команда SSH-ключа деплоя в authorized_keys
# (строку добавляет deploy/setup-cd.sh):
#   restrict,command="/opt/competency/deploy/remote-deploy.sh" ssh-ed25519 AAAA... competency-deploy
# Ключ не дает shell: что бы ни прислал клиент, выполнится этот скрипт, а присланная строка
# придет в SSH_ORIGINAL_COMMAND и разбирается ниже. Допустимы ровно две команды:
#   demo [коммит]    – демо-стенд: коммит main и его образ ghcr.io/...:sha-<коммит> из CI;
#                      без коммита – свежий main, образ собирается на сервере (дольше)
#   prod 1.2.3       – прод на образ ghcr.io/viteax/competency-assessment:1.2.3
set -eu

# Прод – копия репозитория, в которой лежит этот скрипт; демо – рядом, с суффиксом -demo.
PROD_DIR=$(cd "$(dirname "$0")/.." && pwd)
DEMO_DIR="$PROD_DIR-demo"
IMAGE=ghcr.io/viteax/competency-assessment

set -f # без подстановки имен файлов: строка пришла снаружи
# shellcheck disable=SC2086 # разбиваем строку на слова намеренно
set -- ${SSH_ORIGINAL_COMMAND:-}
target="${1:-}"
version="${2:-}"

case "$target" in
demo)
    # Коммит – 7–40 шестнадцатеричных знаков: строка приходит снаружи.
    commit="$version"
    [ -z "$commit" ] || echo "$commit" | grep -Eqx '[0-9a-f]{7,40}' || {
        echo "ожидается коммит, получено: '$commit'" >&2
        exit 2
    }
    cd "$DEMO_DIR"
    git fetch -q origin main
    git reset -q --hard "${commit:-origin/main}"
    # Свой постоянный SECRET_KEY: без него сессии демо сбрасываются при каждом обновлении.
    [ -f .env ] || (
        umask 077
        echo "SECRET_KEY=$(head -c 48 /dev/urandom | base64 | tr -d '\n/+=')" > .env
    )
    compose="docker compose -f docker-compose.demo.yml"
    if [ -n "$commit" ]; then
        # Образ уже собран и проверен в CI: только скачать (секунды вместо сборки).
        image="$IMAGE:sha-$(echo "$commit" | cut -c1-7)"
        if grep -q '^DEMO_IMAGE=' .env; then
            sed -i "s|^DEMO_IMAGE=.*|DEMO_IMAGE=$image|" .env
        else
            echo "DEMO_IMAGE=$image" >> .env
        fi
        $compose pull -q demo-api
        $compose up -d --remove-orphans --wait
    else
        DEMO_IMAGE=competency-demo:local $compose up -d --build --remove-orphans --wait
    fi
    # Демо-данные загружаются только в пустую базу: повторный запуск ничего не меняет.
    $compose exec -T demo-api python -m scripts.seed
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

    echo "→ версии из GitHub"
    # --force: теги на сервере – только копия тегов GitHub; тег, созданный здесь вручную,
    # иначе молча (с -q) остановил бы обновление.
    git fetch -q --tags --force origin || {
        echo "не удалось получить теги из GitHub" >&2
        exit 1
    }
    # В версиях до автоматического обновления нет этого скрипта: после переключения на них
    # ключ деплоя перестал бы работать. На такие версии откатывайте вручную.
    git cat-file -e "v$version:deploy/remote-deploy.sh" 2>/dev/null || {
        echo "v$version не найдена или старше автоматического обновления," \
            "откатывайте вручную (docs/deploy.md, раздел 7)" >&2
        exit 2
    }

    echo "→ резервная копия перед обновлением"
    $compose exec -T backup sh /usr/local/bin/backup.sh

    echo "→ код и конфигурация версии v$version"
    caddyfile=$(git rev-parse HEAD:deploy/Caddyfile)
    git checkout -q "v$version"

    echo "→ образ $IMAGE:$version"
    if grep -q '^APP_IMAGE=' .env; then
        sed -i "s|^APP_IMAGE=.*|APP_IMAGE=$IMAGE:$version|" .env
    else
        echo "APP_IMAGE=$IMAGE:$version" >> .env
    fi
    $compose pull api
    $compose up -d --remove-orphans # миграции применятся при старте api
    # Caddyfile подключен в контейнер файлом: новую версию Caddy увидит только после перезапуска.
    [ "$(git rev-parse HEAD:deploy/Caddyfile)" = "$caddyfile" ] || $compose restart caddy
    echo "prod: v$version"
    ;;
*)
    echo "использование: demo [коммит] | prod <версия>" >&2
    exit 2
    ;;
esac
