# Кабинет администратора по циклу работы кафедры – план

> **Для исполнителя:** superpowers:executing-plans. Шаги отмечаются чекбоксами.

**Цель:** меню «Подготовка → Банк вопросов → Тесты → Результаты → Люди → Система», одно направление в шапке, единая загрузка документов, карточка студента.

**Архитектура:** только фронтенд (`app/static`). Выбор направления – существующие `currentDirection` / `rememberDirection` / `directionPicker` из `admin/directions.js`, поверх них панель в шапке (`mountDirectionBar`, `refreshDirectionBar`) и обёртка экранов `withDirection`. Смена направления – `reload()` из `core.js` (перезапуск текущего экрана). Сервер и API не меняются.

**Стек:** ES-модули без сборки, `h()`, CSP без inline-стилей; e2e на Playwright.

**Спека:** задание заказчика в начале сессии (брейншторм не нужен).

## Глобальные ограничения
- Только короткое тире «–»; тексты по-русски; стили классами в `style.css`.
- Кабинеты студента и преподавателя не трогать; серверный код не менять.
- Старые адреса `#/catalogs/…` не открываются (редиректов нет).

## Review Focus
- Направлений нет: экраны Подготовки, Банка, Тестов, Результатов, Групп показывают подсказку «Система → Направления», а не падают.
- Загрузка учебного плана нового направления переключает шапку на него.
- `#/results/student/<id>` открывается напрямую после перезагрузки и подсвечивает «Результаты».
- Не-план `.xlsx` (матрица компетенций) по-прежнему идёт по пути ОПОП / РПД.
- Удаление выбранного направления: шапка переходит на первое оставшееся.

## Задачи
### Task 1: ядро – `reload`, маршруты, панель направления
Файлы: `core.js` (`reload`, `openAddress` смотрит `routes` и у пунктов меню), `directions.js` (`activeDirection`, `mountDirectionBar`, `refreshDirectionBar`, `unmountDirectionBar`, `withDirection(title, screen)`, `directionTab(tab)` без picker, `loadTests(direction)`), `index.html` (`#direction`), `style.css`.
- [ ] реализовать; [ ] коммит.

### Task 2: загрузка документов
Файлы: `plan-import.js` (`previewPlan(file, slot)`, шапка переключается сразу после загрузки), `import.js` (`previewCompetencies(direction, file, slot)`), новый `document-import.js` (`documentImportView`).
- [ ] реализовать; [ ] коммит.

### Task 3: экраны по направлению
`catalogs.js` (Группы по направлению, обновление шапки при правке направлений), `questions.js`, `assign.js`, `tests.js`, `students.js`, `results.js` (`adminGroupResults`, `studentScreen`, `studentCardScreen(id)`; `adminLaborFunctions` удалить).
- [ ] реализовать; [ ] коммит.

### Task 4: меню и страницы
`pages.js` (`prepPage`, `peoplePage`, `systemPage`, `testsPage`), `main.js` (ADMIN_MENU, ROUTES.admin, панель в шапке), `home.js`, тексты-подсказки.
- [ ] реализовать; [ ] коммит.

### Task 5: тесты и документы
Обновить e2e (`test_navigation`, `test_admin_edit`, `test_home`, `test_imports`, `test_main_flow`, `test_residual_knowledge`, `test_registration`, `test_security`, `test_teacher`), добавить `test_admin_cycle.py` (смена направления; карточка студента и прямой адрес), README, CHANGELOG, `.gitignore`.
- [ ] прогнать pytest, e2e, ruff, ESLint; [ ] коммит; [ ] ручной проход на демо.
