# CLAUDE.md

Система оценки сформированности компетенций студентов (кафедра, ТУСУР). Заказчик – Лариошина.
Подробности для людей – в `README.md`, развёртывание – в `docs/deploy.md`, история – в `CHANGELOG.md`.

## Правила работы
- Отвечать по-русски.
- Только короткое тире «–», никогда длинное (U+2014): в ответах, коде, комментариях, текстах интерфейса,
  документации и коммитах. Исключение – парсер компетенций, где длинное тире во входных файлах
  записано как `\u2014`.
- Работаем прямо в `main`. Pull request не создавать без просьбы. Без force-push и переписывания
  истории без явного согласия.
- После пуша проверять CI примерно через 2 минуты (он идёт около двух минут). Смотреть все свежие
  запуски, а не только последний.
- Изменения записывать в `CHANGELOG.md` в раздел «Не выпущено». При изменении API или интерфейса
  обновлять `README.md`.

## Стек
- Python 3.12 + uv, FastAPI, SQLAlchemy 2, Alembic, pydantic 2, python-docx, openpyxl.
- PostgreSQL 16 в проде, SQLite для тестов и демо.
- Фронтенд – чистые ES-модули без сборки (`app/static/js`), CSP без inline-стилей и скриптов.

## Структура
- `app/api/` – тонкие роутеры; запросы к БД и логика – в `app/services/`.
- `app/schemas/` – pydantic-схемы по разделам, реэкспорт в `app/schemas/__init__.py`.
- `app/models.py` – модели; после правки – миграция в `migrations/versions/`.
- `app/validation_messages.py` – перевод ошибок 422 на русский (введённые значения не выводятся).
- `app/static/js/core.js` – `h()` / `fill()`, `api()`, `go(view, menuItem)`, `tabbedPage()`,
  `screenTab()`. Разметку строить через `h()`, стили – классами в `app/static/style.css`.
- Адрес экрана – в хэше (`#/раздел/вкладка`, `#/test/5`): у пунктов меню он третий элемент
  в `main.js`, у вкладок – часть названия, экран с параметром создаётся через
  `screenAt(path, view, menuItem)` и регистрируется в `ROUTES` в `main.js`. `onLeave()` –
  что сделать при уходе с экрана.
- `app/static/js/admin/` – экраны администратора; меню в `main.js` (`ADMIN_MENU`),
  разделы с вкладками – в `admin/pages.js`, главная – `admin/home.js`.
- Роли: администратор, преподаватель (`teacher.js`), студент (`student.js`).
- Типы заданий только три: `matching`, `sequence`, `open`.
- `scripts/seed.py` и `scripts/demo_questions.py` – демо-данные (учётки `admin`/`admin123`,
  `teacher`/`teacher123`, `student1..3`/`student123`, только при `ENVIRONMENT=dev`).

## Команды
```bash
uv sync && npm ci                                   # зависимости
ENVIRONMENT=dev DATABASE_URL=sqlite:///./competency.db uv run python -m scripts.seed
ENVIRONMENT=dev DATABASE_URL=sqlite:///./competency.db uv run uvicorn app.main:app --reload

uv run pytest -q -n auto                            # юнит-тесты (параллельно)
E2E_CHROMIUM=/opt/pw-browsers/chromium uv run pytest -m e2e -n auto   # браузерные (Playwright)
uv run ruff check . && uv run ruff format --check . # линтер Python
npm run lint -- --max-warnings 0                    # ESLint фронтенда

uv run alembic revision --autogenerate -m "..."     # новая миграция
uv run python -m scripts.release 2.0.1             # выпуск: версия + раздел CHANGELOG
                                                    # (или кнопка Actions → Release)
```
Миграции проверять и на PostgreSQL: `pg_ctlcluster 16 main start`, база `migcheck`,
`upgrade head` → `check` → `downgrade` → `upgrade`.

## CI (`.github/workflows/ci.yml`)
Джобы: test, e2e, frontend (ESLint + npm audit), audit (pip-audit), migrations (PostgreSQL),
docker. Перед пушем прогнать локально юнит-тесты, e2e, ruff и ESLint.
