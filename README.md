# Competency Assessment

Сервис тестирования студентов по компетенциям ФГОС (УК, ОПК, ПК) с привязкой
результатов к трудовым функциям профстандарта (например, 06.001 «Программист»).

## Идея

```
Учебный план ─► Дисциплины ─► Компетенции (УК / ОПК / ПК) ─► Индикаторы
                                    │
                                    ├─► Банк вопросов ─► Тест ─► Назначение группе ─► Попытка студента
                                    │
Профстандарт ─► ОТФ ─► ТФ ◄─────────┘  (ТФ ⇒ ПК: какие компетенции нужны для трудовой функции)
```

1. **Администратор** выбирает компетенции (например, ОПК-5, ПК-1) и собирает тест:
   по N вопросов на каждую компетенцию, равномерно по её индикаторам.
2. Назначает тест **группе**.
3. **Студент** проходит тест и получает балл (например, 5/6).
4. По результатам строятся отчёты:
   - доля верных ответов по каждой компетенции (порог «сформирована» — `MASTERY_THRESHOLD`,
     по умолчанию 60%);
   - **ПК → ОТФ**: какие трудовые функции профстандарта студент закрывает. ТФ закрыта,
     если сформированы все связанные с ней компетенции, ОТФ — если закрыты все её ТФ.

## Стек

Python 3.12+, FastAPI, SQLAlchemy 2, PostgreSQL, Pydantic 2, Pytest.

## Запуск

```bash
docker compose up --build
docker compose exec api python -m scripts.seed   # демо-данные
```

Документация API: http://localhost:8000/docs (кнопка **Authorize** — вход по логину и паролю).

Демо-учётки из `seed`: `admin` / `admin123`, `student1`…`student3` / `student123`.
Для реального развёртывания задайте `SECRET_KEY` и создайте администратора:

```bash
docker compose exec api python -m scripts.create_admin <логин>
```

Локально без Docker:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/competency
python -m scripts.seed          # создаёт таблицы и заполняет демо-данными
uvicorn app.main:app --reload
```

Тесты используют SQLite в памяти, PostgreSQL для них не нужен:

```bash
pytest
```

## Роли и API

Авторизация — JWT (`Authorization: Bearer <token>`), токен выдаёт `POST /auth/token`
(OAuth2 password flow). Две роли:

- **admin** — справочники, банк вопросов, сборка и назначение тестов, отчёты, пользователи;
- **student** — только свои назначения, прохождение тестов и свои результаты. Учётка студента
  привязана к записи в списке студентов, поэтому `student_id` берётся из токена, а не из запроса.

| Роль | Метод | Путь | Назначение |
| :-- | :-- | :-- | :-- |
| все | `POST` | `/auth/token` | Вход, получение токена |
| все | `GET` | `/me` | Текущий пользователь |
| admin | `POST/GET` | `/users` | Учётные записи (студенту указывается `student_id`) |
| admin | `POST/GET` | `/directions`, `/groups`, `/students` | Направления, группы, студенты (ФИО + группа) |
| admin | `POST/GET` | `/competencies` | Компетенции с индикаторами |
| admin | `POST/GET` | `/disciplines` | Дисциплины и формируемые ими компетенции |
| admin | `POST/GET` | `/standards` | Профстандарт с ОТФ и ТФ |
| admin | `PUT` | `/labor-functions/{id}/competencies` | Связь ТФ ⇒ компетенции |
| admin | `POST/GET` | `/questions` | Банк вопросов (один правильный вариант) |
| admin | `POST` | `/tests` | Собрать тест по компетенциям |
| admin | `POST` | `/assignments` | Назначить тест группе |
| admin | `GET` | `/reports/students/{id}/competencies` | Результаты студента по компетенциям |
| admin | `GET` | `/reports/students/{id}/labor-functions` | Закрытые ОТФ / ТФ профстандарта |
| admin | `GET` | `/reports/groups/{id}/competencies` | Сводка по группе |
| student | `GET` | `/me/assignments` | Назначенные мне тесты |
| student | `POST` | `/me/attempts` | Начать попытку (вопросы без правильных ответов) |
| student | `POST` | `/me/attempts/{id}/submit` | Сдать ответы, получить балл |
| student | `GET` | `/me/reports/competencies` | Мои результаты по компетенциям |
| student | `GET` | `/me/reports/labor-functions` | Мои закрытые ОТФ / ТФ |

## Структура

```
app/
  models.py        модель данных
  security.py      хеширование паролей (scrypt) и JWT
  schemas.py       Pydantic-схемы запросов и ответов
  api/             роутеры FastAPI
  services/        сборка тестов, проверка ответов, отчёты
scripts/
  init_db.py       создание таблиц
  create_admin.py  создание администратора
  seed.py          демо-данные (формулировки примерные)
tests/
```

## Дальше

- Миграции Alembic вместо `create_all`
- Импорт компетенций и учебного плана из файлов ОПОП / РПД
- Веб-интерфейс администратора и студента
- Ограничение по времени на попытку, вопросы с несколькими правильными ответами
