# Учебные планы и добавление преподавателей: план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** у одного кода направления может быть несколько учебных планов (код + программа + год), а преподаватели добавляются списком ФИО с логином «Фамилия И.О.».

**Architecture:** `Direction` остаётся моделью и таблицей, но теперь это план: добавляются `profile`, `plan_year`, вычисляемый `profile_key` и свойство `label`. Вся связка данных через `direction_id` не меняется. Преподаватели – новый массовый эндпоинт, логин строится на сервере.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pydantic 2, ES-модули без сборки.

**Spec:** `docs/superpowers/specs/2026-10-30-curriculum-plans-design.md`

## Global Constraints

- Только короткое тире «–» в коде, текстах и коммитах.
- Интерфейс и сообщения об ошибках – по-русски; разметка через `h()`, без inline-стилей.
- Роутеры тонкие, логика в `app/services/`.
- Миграции работают на PostgreSQL 16 и SQLite.
- Существующие данные не удаляются и не перепривязываются.
- Команды запускать через `.venv\Scripts\python.exe -m ...` (`uv` не в PATH). E2E и проверка на PostgreSQL локально на Windows не работают: их проверяет CI ветки (джобы e2e, migrations).
- Работа в ветке `plans-and-teachers` в worktree; слияние в `main` и действия на сервере – только после «да» пользователя.

## Review Focus

- Повторная загрузка плана, где программа написана иначе («Управление  разработками», другой регистр, «ё») – дубля нет. Тест в задаче 2.
- В `Титул` нет года или программы – предпросмотр предупреждает, загрузка работает, план можно дополнить позже. Тест в задаче 2.
- Перевод группы с назначенным тестом – понятная ошибка; смена только названия или года такой группы – работает. Тест в задаче 3.
- В списке преподавателей пустые строки, двойные пробелы, повтор в одном списке, только фамилия – остальные строки не теряются. Тест в задаче 6.
- Новый логин мигрирующего преподавателя совпал с уже занятым (дубль Ботаевой) – миграция не падает. Тест в задаче 7.

---

### Task 1: Модель и миграция плана

**Files:**
- Modify: `app/models.py:104-114`, `app/schemas/study.py`, `app/api/study.py:14-34`
- Create: `migrations/versions/20261030_<rev>_direction_plans.py`
- Test: `tests/test_directions.py`, `tests/test_migrations.py`

**Interfaces:**
- Produces: `models.profile_key(text: str | None) -> str`; `Direction.profile: str | None`, `Direction.plan_year: int | None`, `Direction.profile_key: str`, `Direction.label: str`, `Direction.intake_years: list[int]`; `DirectionOut` с полями `profile`, `plan_year`, `label`, `intake_years`; `DirectionIn` с необязательными `profile`, `plan_year`.

- [ ] **Step 1: Тесты**

```python
def test_two_plans_same_code(admin):
    a = admin.post(
        "/directions",
        json={"code": "11.03.02", "name": "Связь", "profile": "Оптика", "plan_year": 2023},
    )
    b = admin.post(
        "/directions",
        json={"code": "11.03.02", "name": "Связь", "profile": "Оптика", "plan_year": 2026},
    )
    assert a.status_code == b.status_code == 201
    assert a.json()["label"] == "11.03.02 Связь, Оптика, 2023"


def test_same_triple_conflicts_even_with_empty_fields(admin):
    body = {"code": "11.03.02", "name": "Связь"}
    assert admin.post("/directions", json=body).status_code == 201
    assert admin.post("/directions", json=body).status_code == 409
    assert admin.post("/directions", json={**body, "profile": "опт"}).status_code == 201
    assert admin.post("/directions", json={**body, "profile": " ОПТ "}).status_code == 409


def test_profile_key_ignores_spelling():
    assert profile_key(" «Ёлки»  и Палки ") == profile_key("елки и палки")
    assert profile_key(None) == ""


def test_intake_years_from_groups(
    admin,
): ...  # группы 2025 и 2024 в плане → intake_years == [2024, 2025]
```

Тест миграции: вставить две записи направления на предыдущей ревизии, `upgrade` – поля пустые, данные и `id` на месте; после создания второго плана с тем же кодом `downgrade` падает с ошибкой, в которой есть код направления, и строки не удалены.

- [ ] **Step 2: Запустить, убедиться, что падают**

Run: `.venv\Scripts\python.exe -m pytest tests/test_directions.py -q`
Expected: FAIL (нет полей). Существующий тест на уникальность кода, если есть, переписать под тройку.

- [ ] **Step 3: Реализовать**

`profile_key`: casefold, «ё»→«е», убрать кавычки `"«»„“'`, схлопнуть пробелы. `profile_key` колонка `String(255) NOT NULL server_default ''`, заполняется через `@validates("profile")`. Индекс: `Index("uq_direction_plan", "code", "profile_key", text("coalesce(plan_year, 0)"), unique=True)`, уникальность с `code` снять. `label`: `f"{code} {name}"` + `, {profile}` + `, {plan_year}`, пустые части опускаются. `intake_years`: отсортированные уникальные `start_year` групп без `None`. Дополнительно `Group.direction` остаётся как есть.

Миграция – вручную (`batch_alter_table` для SQLite); `downgrade` сначала проверяет дубли `code` и поднимает `RuntimeError` с их перечнем.

- [ ] **Step 4: Прогнать**

Run: `.venv\Scripts\python.exe -m pytest tests/test_directions.py tests/test_migrations.py -q`, затем `.venv\Scripts\python.exe -m alembic check`
Expected: PASS, новых изменений схемы нет. Если `check` спотыкается на выражении в индексе – исключить индекс через `include_object` в `migrations/env.py`.

- [ ] **Step 5: Коммит** – `Учебный план: программа и год у направления`

### Task 2: Загрузка плана из Excel

**Files:**
- Modify: `app/services/plan_import.py:373-376,532-562`, `app/schemas/plan_import.py`, `app/api/imports.py:48-60`, `app/static/js/admin/plan-import.js`
- Test: `tests/test_plan_import.py` (образец из `tests/import_samples.py`, при необходимости добавить аргументы программы и года)

**Interfaces:**
- Consumes: `models.profile_key`, `Direction.label`.
- Produces: `PlanDirection.label: str`, `PlanPreview.candidates: list[PlanCandidate]` (`id`, `label`); `plan_import.apply(session, plan, overwrite_descriptions, merge_into: int | None = None, create_new: bool = False)`; те же поля формы в `/apply`.

- [ ] **Step 1: Тесты**

```python
# upload(admin, profile, year, **form) – загрузка образца; preview(admin, profile, year) – предпросмотр
def test_same_triple_updates(admin): ...  # второй раз – created_direction False, планов один
def test_spelling_of_profile_no_duplicate(admin): ...  # «ОПТИКА » и «оптика» – один план
def test_other_year_creates_plan_without_question(
    admin,
): ...  # 2023 и 2026: candidates пуст, два плана
def test_empty_plan_is_candidate(admin):
    admin.post("/directions", json={"code": CODE, "name": "X"})
    assert [c["id"] for c in preview(admin, "П", 2023)["candidates"]]
    r = upload(admin, "П", 2023)  # ничего не выбрано
    assert r.status_code == 422 or r.status_code == 409


def test_merge_into_fills_fields(
    admin,
): ...  # merge_into=id: у плана profile и plan_year из файла, id тот же
def test_create_new_keeps_old(admin): ...  # create_new=true: два плана, старый пуст
def test_file_without_year_warns(
    admin,
): ...  # warnings содержит «год», загрузка проходит, plan_year None
def test_merge_into_conflicting_plan_rejected(admin): ...  # заполненные поля расходятся – ошибка
```

- [ ] **Step 2: Запустить, убедиться, что падают**

Run: `.venv\Scripts\python.exe -m pytest tests/test_plan_import.py -q`

- [ ] **Step 3: Реализовать**

`_existing` ищет план по `code`, `profile_key`, `plan_year`. `_candidates(session, plan)`: планы того же кода, кроме точного совпадения, где каждое заполненное у обеих сторон поле совпадает, а хотя бы одно пустое. При точном совпадении кандидаты не показываются. `apply`: кандидаты есть, а `merge_into` и `create_new` не заданы – `DomainError`; `merge_into` не из кандидатов – `DomainError`; при слиянии заполнить пустые поля. Создание нового плана сохраняет `profile` и `plan_year`. В `parse` предупреждение, если нет программы или года. `preview` принимает те же решения, чтобы подсчёты статусов соответствовали выбранному варианту, но без выбора считает как для нового плана.

Фронтенд: при `candidates` показать радиокнопки «Дополнить „label“» / «Создать новый план», кнопка сохранения неактивна, пока нет выбора. Заголовок – `d.label`.

- [ ] **Step 4: Прогнать** – те же тесты, PASS.
- [ ] **Step 5: Коммит** – `Загрузка УП: разные программы и годы одного кода`

### Task 3: Группы, импорт студентов и вопросов

**Files:**
- Modify: `app/api/study.py:50-54`, `app/services/catalogs.py` (сервис перевода), `app/services/student_import.py:113-156`, `app/services/fund_import.py:536-568,770-771`, `app/schemas/fund_import.py`, `app/static/js/admin/fund-import.js`
- Test: `tests/test_directions.py`, `tests/test_student_import.py`, `tests/test_fund_import.py`

**Interfaces:**
- Consumes: `Direction.label`.
- Produces: поле предпросмотра ФОС `target_label: str | None`, предупреждение о несовпадении в `warnings`.

- [ ] **Step 1: Тесты**

```python
def test_move_group_without_assignments(admin): ...  # PUT с другим direction_id – 200
def test_move_group_with_assignment_conflict(admin): ...  # 409, текст про назначенные тесты
def test_rename_group_with_assignment_ok(admin): ...  # direction_id тот же – 200
def test_student_import_new_group_goes_to_selected_plan(
    admin,
): ...  # два плана кода, программа в файле совпадает с кодом – группа в выбранном
def test_fund_prefers_selected_plan(
    admin,
): ...  # два плана кода, direction_id=второй – вопросы в нём
def test_fund_ambiguous_without_match(
    admin,
): ...  # выбран план другого кода, с кодом документа два плана – ошибка «выберите план в шапке»
def test_fund_other_code_single_plan_warns(
    admin,
): ...  # единственный план с кодом документа – берётся он, warnings и target_label
```

- [ ] **Step 2: Запустить, убедиться, что падают**
- [ ] **Step 3: Реализовать**

`update_group`: если `direction_id` меняется и у группы есть `Assignment` – `Conflict("группе уже назначены тесты: они ссылаются на вопросы другого плана. Перевести такую группу нельзя")`. Новая логика `_target` без дисциплины: нет кода в документе или код совпал с выбранным – выбранный; иначе планы с кодом документа: один – он с предупреждением, несколько – ошибка, ни одного – текущая ошибка (с заменой «направление» на «учебный план»). `direction_for_program`: при заданном `data.direction_id` выбранный план приоритетнее; без него код из программы подходит, только если план единственный.

- [ ] **Step 4: Прогнать** – `.venv\Scripts\python.exe -m pytest tests/test_directions.py tests/test_student_import.py tests/test_fund_import.py -q`, PASS.
- [ ] **Step 5: Коммит** – `Группы и импорт документов: выбранный план`

### Task 4: Подписи планов и интерфейс

**Files:**
- Modify: `app/services/reports.py:104`, `diagnostic_report.py:153`, `fund.py:26`, `dashboard.py:120`, `teaching.py:72,89`, `catalogs.py:24,48,96`, `fund_import.py:566`
- Modify: `app/static/js/admin/directions.js`, `catalogs.js:190-228`, `pages.js`, `import.js:177`, `main.js` (пункт меню, если есть текст), тексты «Направление» в `app/static/js/admin/*.js` и `teacher.js`
- Test: `tests/test_word_export.py`, `tests/test_teacher.py`, `tests/e2e/test_admin_cycle.py`

**Interfaces:**
- Consumes: `Direction.label`, `DirectionOut.label`, `intake_years`.
- Produces: `directionLabel = (d) => d.label`.

- [ ] **Step 1: Тесты**

```python
def test_report_and_word_show_plan_label(
    admin,
): ...  # у плана profile и plan_year: в шапке Word и заголовке отчёта есть программа и год
def test_teacher_sees_plan_label(
    admin, teacher
): ...  # в /teacher/disciplines поле direction содержит год
```

E2E: загрузить два плана с одним кодом, переключить в шапке, убедиться, что список дисциплин разный. Обновить тексты e2e, где ищется «Направление».

- [ ] **Step 2: Запустить, убедиться, что падают**
- [ ] **Step 3: Реализовать**

Заменить склейки «код название» на `label`. Интерфейс: вкладка «Система → Учебные планы», поля «Код», «Название», «Программа», «Год плана» (последние два необязательные), колонка «Годы набора» из `intake_years`; шапка «Учебный план»; в списке – сначала код, затем год по убыванию (`api/study.py:21`). Текст `NO_DIRECTION` и пояснения в `pages.js`. Ключи маршрутов (хэш) меняются вместе с названиями вкладок: проверить `tests/e2e`.

- [ ] **Step 4: Прогнать**

Run: `.venv\Scripts\python.exe -m pytest -q -n auto`, `npm run lint -- --max-warnings 0`, `.venv\Scripts\python.exe -m ruff check .`, `.venv\Scripts\python.exe -m ruff format --check .`
Expected: всё зелёное.

- [ ] **Step 5: Коммит** – `Интерфейс: учебные планы вместо направлений`

### Task 5: Вход преподавателя по фамилии и инициалам

**Files:**
- Modify: `app/services/accounts.py`, `app/services/auth.py:111-122`
- Test: `tests/test_security.py`

**Interfaces:**
- Produces: `accounts.teacher_login(full_name: str) -> str`; `accounts.unique_teacher_login(session, full_name, taken: set[str]) -> str`; `auth.login_key(text: str) -> str`.

- [ ] **Step 1: Тесты**

```python
def test_teacher_login():
    assert teacher_login("Ханкишиева Наиля Рамизовна") == "Ханкишиева Н.Р."
    assert teacher_login("  Иванов   Иван ") == "Иванов И."
    assert teacher_login("Иванов") == "Иванов"

@pytest.mark.parametrize("typed", ["Ханкишиева Н.Р.", "ханкишиева н.р.", "Ханкишиева Н. Р.", "ханкишиева нр"])
def test_teacher_can_log_in_with_any_spelling(client, teacher_account, typed): ...

def test_student_login_not_affected(...): ...  # вход студента по ФИО как раньше
```

- [ ] **Step 2: Запустить, убедиться, что падают**
- [ ] **Step 3: Реализовать**

`login_key`: casefold, «ё»→«е», удалить точки и пробелы. `find_user`: точное совпадение, затем поиск студента как сейчас, затем среди преподавателей по `login_key`; условие «есть пробел» оставить, чтобы цифровые и латинские логины шли только точным сравнением. Дополнение суффиксом: «Иванов И.И.2», «Иванов И.И.3».

- [ ] **Step 4: Прогнать** – `.venv\Scripts\python.exe -m pytest tests/test_security.py -q`, PASS.
- [ ] **Step 5: Коммит** – `Логин преподавателя – фамилия и инициалы`

### Task 6: Добавление преподавателей списком

**Files:**
- Modify: `app/api/auth.py`, `app/services/accounts.py`, `app/schemas/users.py`, `app/static/js/admin/catalogs.js:282-356`, `app/static/js/core.js` (при необходимости), `app/static/style.css`
- Test: `tests/test_teacher.py`, `tests/e2e/test_admin_cycle.py`

**Interfaces:**
- Consumes: `unique_teacher_login`, `ensure_new_staff_name`, `generate_password`.
- Produces: `POST /users/teachers` (только админ), тело `TeachersIn{full_names: list[str]}` (до 200), ответ `TeachersResult{created: list[TeacherCreated{full_name, username, password}], skipped: list[TeacherSkipped{full_name, reason}]}`.

- [ ] **Step 1: Тесты**

```python
def test_bulk_creates_with_passwords(admin):
    r = admin.post(
        "/users/teachers", json={"full_names": ["Иванов Иван Иванович", "", "  Петров   Пётр "]}
    ).json()
    assert [t["username"] for t in r["created"]] == ["Иванов И.И.", "Петров П."]
    assert all(t["password"] for t in r["created"])


def test_bulk_skips_duplicates_and_keeps_rest(
    admin,
): ...  # повтор в списке и уже существующий – в skipped с причиной, новые создаются
def test_bulk_namesakes_get_number(
    admin,
): ...  # «Иванов Иван Ильич» и «Иванов Игорь Ильич» → «Иванов И.И.», «Иванов И.И.2»
def test_bulk_forces_password_change(admin): ...  # must_change_password True
def test_bulk_requires_admin(client, teacher): ...  # 403
def test_bulk_short_name_skipped(admin): ...  # логин короче 3 символов – в skipped
```

- [ ] **Step 2: Запустить, убедиться, что падают**
- [ ] **Step 3: Реализовать**

Сервис сохраняет всё одной транзакцией после разбора строк. Фронтенд: вместо полей ФИО и логина – `textarea` «ФИО, по одному на строку» и кнопка «Добавить»; ниже результат: таблица ФИО, логин, пароль, кнопка «Скопировать всё» (`navigator.clipboard.writeText`, строки через табуляцию), предупреждение «Пароли показываются один раз», список пропущенных с причиной. Результат не исчезает при перерисовке списка. Старый `POST /users` остаётся для совместимости. Обновить пояснение вкладки.

- [ ] **Step 4: Прогнать** – `.venv\Scripts\python.exe -m pytest tests/test_teacher.py -q`, PASS.
- [ ] **Step 5: Коммит** – `Добавление преподавателей списком ФИО`

### Task 7: Перевод цифровых логинов, документация, проверка

**Files:**
- Create: `migrations/versions/20261030_<rev>_teacher_logins.py`
- Modify: `README.md`, `CHANGELOG.md`, `docs/deploy.md` (если есть упоминания), `scripts/seed.py` (если нужны поля плана в демо)
- Test: `tests/test_migrations.py`

**Interfaces:**
- Consumes: формат логина из задачи 5 (в миграции функция копируется, код приложения из миграции не импортируется).

- [ ] **Step 1: Тест миграции**

```python
def test_digit_teacher_logins_converted(...):
    # 111 Ханкишиева Наиля Рамизовна, 666 и 999 Ботаева Лариса Борисовна, teacher Тест Тест Тест, 1 admin
    # после upgrade: «Ханкишиева Н.Р.», «Ботаева Л.Б.» и «Ботаева Л.Б.2»; teacher и 1 не изменились; хэши паролей те же
```

- [ ] **Step 2: Запустить, убедиться, что падает**
- [ ] **Step 3: Реализовать**

Только `role='teacher'`, логин из одних цифр, непустое ФИО, порядок по `id`. Занятый логин даёт суффикс. `downgrade` – без действий: старые логины не хранятся, в докстринге это объяснено.

- [ ] **Step 4: Документация**

`CHANGELOG.md`, раздел «Не выпущено»: учебные планы, добавление преподавателей, изменение логинов. `README.md`: разделы про направления и преподавателей, новый эндпоинт.

- [ ] **Step 5: Полная проверка**

Run: `.venv\Scripts\python.exe -m pytest -q -n auto`, `ruff check`, `ruff format --check`, `npm run lint -- --max-warnings 0`, `alembic check`
Expected: всё зелёное.

- [ ] **Step 6: Коммит и пуш ветки** – `Миграция логинов преподавателей, документация`

Пуш ветки, дождаться CI (test, e2e, frontend, audit, migrations, docker) по хешу коммита. Слияние в `main` – после «да» пользователя.
