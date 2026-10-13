"""Заполняет БД демонстрационными данными.

Направление, группа со студентами, несколько компетенций с индикаторами, дисциплины,
фрагмент профстандарта 06.001 «Программист» и банк вопросов. Формулировки компетенций
и вопросов — примерные, для реального УП их нужно заменить на формулировки из ФГОС/ОПОП.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import SessionLocal
from app.demo import DEMO_ADMIN, DEMO_STUDENT_COUNT, DEMO_STUDENT_PASSWORD
from app.models import CompetencyKind as K
from app.security import hash_password
from scripts.init_db import migrate

COMPETENCIES = [
    (
        "УК-1",
        K.UK,
        "Способен осуществлять поиск, критический анализ и синтез информации",
        [
            ("УК-1.1", "Знает методы критического анализа и синтеза информации"),
            ("УК-1.2", "Умеет применять системный подход для решения задач"),
        ],
    ),
    (
        "ОПК-1",
        K.OPK,
        "Способен применять естественнонаучные и общеинженерные знания, методы "
        "математического анализа и моделирования",
        [
            ("ОПК-1.1", "Знает основы математики, физики, вычислительной техники"),
            (
                "ОПК-1.2",
                "Умеет решать стандартные профессиональные задачи с применением "
                "математических методов",
            ),
        ],
    ),
    (
        "ОПК-5",
        K.OPK,
        "Способен инсталлировать программное и аппаратное обеспечение",
        [
            ("ОПК-5.1", "Знает основы системного администрирования"),
            ("ОПК-5.2", "Умеет устанавливать программное обеспечение"),
        ],
    ),
    (
        "ПК-1",
        K.PK,
        "Способен разрабатывать и отлаживать программный код",
        [
            ("ПК-1.1", "Знает синтаксис и методы отладки выбранного языка программирования"),
            ("ПК-1.2", "Умеет писать и отлаживать программный код"),
        ],
    ),
    (
        "ПК-2",
        K.PK,
        "Способен проверять работоспособность и выполнять рефакторинг кода",
        [
            ("ПК-2.1", "Знает методы тестирования программного обеспечения"),
            ("ПК-2.2", "Умеет выполнять рефакторинг и оптимизацию кода"),
        ],
    ),
]

DISCIPLINES = {
    "Математика": ["ОПК-1", "УК-1"],
    "Операционные системы": ["ОПК-5"],
    "Программирование": ["ПК-1", "ПК-2", "УК-1"],
}

STANDARD = (
    "06.001",
    "Программист",
    [
        (
            "A",
            "Разработка и отладка программного кода",
            3,
            [
                ("A/01.3", "Формализация и алгоритмизация поставленных задач", ["ОПК-1", "ПК-1"]),
                (
                    "A/02.3",
                    "Написание программного кода с использованием языков программирования",
                    ["ПК-1"],
                ),
                (
                    "A/03.3",
                    "Оформление программного кода в соответствии с установленными требованиями",
                    ["ПК-1"],
                ),
            ],
        ),
        (
            "B",
            "Проверка работоспособности и рефакторинг кода программного обеспечения",
            4,
            [
                (
                    "B/01.4",
                    "Разработка процедур проверки работоспособности и измерения характеристик "
                    "программного обеспечения",
                    ["ПК-2"],
                ),
                ("B/02.4", "Разработка тестовых наборов данных", ["ПК-2"]),
                (
                    "B/03.4",
                    "Проверка работоспособности программного обеспечения",
                    ["ПК-2", "ОПК-5"],
                ),
            ],
        ),
    ],
)

# (индикатор, дисциплина, вопрос, [варианты], индекс правильного)
QUESTIONS = [
    ("ОПК-1.1", "Математика", "Чему равна производная функции x²?", ["2x", "x", "x³/3", "2"], 0),
    (
        "ОПК-1.1",
        "Математика",
        "Сколько элементов в множестве всех подмножеств множества из 3 элементов?",
        ["3", "6", "8", "9"],
        2,
    ),
    ("ОПК-1.1", "Математика", "Определитель единичной матрицы 3×3 равен", ["0", "1", "3", "9"], 1),
    (
        "ОПК-1.2",
        "Математика",
        "Решение уравнения 2x + 4 = 10",
        ["x = 2", "x = 3", "x = 7", "x = 5"],
        1,
    ),
    (
        "ОПК-1.2",
        "Математика",
        "Вероятность выпадения орла при двух бросках монеты подряд",
        ["1/2", "1/3", "1/4", "1"],
        2,
    ),
    (
        "ОПК-1.2",
        "Математика",
        "Сумма арифметической прогрессии 1 + 2 + … + 10",
        ["45", "50", "55", "100"],
        2,
    ),
    (
        "УК-1.1",
        "Математика",
        "Что из перечисленного является контрпримером к утверждению «все простые числа нечётны»?",
        ["1", "2", "9", "15"],
        1,
    ),
    (
        "УК-1.2",
        "Программирование",
        "Первый шаг системного подхода к решению задачи",
        ["Написать код", "Определить цель и границы системы", "Выбрать язык", "Провести тесты"],
        1,
    ),
    (
        "ОПК-5.1",
        "Операционные системы",
        "Какая команда Linux показывает запущенные процессы?",
        ["ls", "ps", "cd", "mv"],
        1,
    ),
    (
        "ОПК-5.1",
        "Операционные системы",
        "Файл с учётными записями пользователей в Linux",
        ["/etc/passwd", "/var/log", "/home", "/tmp/users"],
        0,
    ),
    (
        "ОПК-5.2",
        "Операционные системы",
        "Менеджер пакетов в Debian/Ubuntu",
        ["yum", "apt", "brew", "pip"],
        1,
    ),
    (
        "ОПК-5.2",
        "Операционные системы",
        "Права на исполнение файла выдаёт команда",
        ["chmod +x", "chown", "mkdir", "touch"],
        0,
    ),
    (
        "ОПК-5.2",
        "Операционные системы",
        "Что делает `systemctl enable nginx`?",
        ["Останавливает nginx", "Включает автозапуск nginx", "Удаляет nginx", "Обновляет nginx"],
        1,
    ),
    (
        "ПК-1.1",
        "Программирование",
        "Что выведет `print(len('abc'))` в Python?",
        ["2", "3", "abc", "Ошибку"],
        1,
    ),
    (
        "ПК-1.1",
        "Программирование",
        "Инструмент пошагового выполнения программы",
        ["Компилятор", "Отладчик", "Линтер", "Профилировщик"],
        1,
    ),
    (
        "ПК-1.2",
        "Программирование",
        "Какая сложность у бинарного поиска?",
        ["O(n)", "O(log n)", "O(n²)", "O(1)"],
        1,
    ),
    (
        "ПК-1.2",
        "Программирование",
        "Какая структура данных работает по принципу LIFO?",
        ["Очередь", "Стек", "Дерево", "Хеш-таблица"],
        1,
    ),
    (
        "ПК-1.2",
        "Программирование",
        "Ключевое слово для объявления функции в Python",
        ["func", "def", "function", "lambda"],
        1,
    ),
    (
        "ПК-2.1",
        "Программирование",
        "Тест, проверяющий отдельную функцию изолированно",
        ["Интеграционный", "Модульный", "Нагрузочный", "Приёмочный"],
        1,
    ),
    (
        "ПК-2.1",
        "Программирование",
        "Что такое регрессионное тестирование?",
        [
            "Проверка, что изменения не сломали работавшее",
            "Тестирование производительности",
            "Тестирование интерфейса",
            "Тестирование безопасности",
        ],
        0,
    ),
    (
        "ПК-2.2",
        "Программирование",
        "Рефакторинг — это",
        [
            "Добавление новой функциональности",
            "Изменение структуры кода без изменения поведения",
            "Исправление ошибок",
            "Удаление тестов",
        ],
        1,
    ),
    (
        "ПК-2.2",
        "Программирование",
        "Приём «извлечение метода» нужен, чтобы",
        [
            "Ускорить компиляцию",
            "Выделить фрагмент кода в отдельную функцию",
            "Удалить дублирующие тесты",
            "Переименовать переменную",
        ],
        1,
    ),
]

STUDENTS = ["Иванов Иван Иванович", "Петрова Анна Сергеевна", "Сидоров Пётр Алексеевич"]

# Демо-учётки (app/demo.py) — только для локального запуска. В проде администратор
# создаётся через `python -m scripts.create_admin`, остальные — в интерфейсе.
ADMIN_LOGIN = DEMO_ADMIN
STUDENT_PASSWORD = DEMO_STUDENT_PASSWORD
assert len(STUDENTS) == DEMO_STUDENT_COUNT


def seed(session: Session) -> None:
    if session.scalar(select(models.Direction).limit(1)):
        print("БД уже заполнена, пропускаю")
        return

    direction = models.Direction(code="09.03.04", name="Программная инженерия")
    group = models.Group(name="ПИ-21", direction=direction)
    group.students = [models.Student(full_name=name) for name in STUDENTS]
    session.add(direction)
    session.add(
        models.User(
            username=ADMIN_LOGIN[0],
            password_hash=hash_password(ADMIN_LOGIN[1]),
            role=models.Role.ADMIN,
        )
    )
    student_hash = hash_password(STUDENT_PASSWORD)
    for i, student in enumerate(group.students, start=1):
        session.add(
            models.User(
                username=f"student{i}",
                password_hash=student_hash,
                role=models.Role.STUDENT,
                student=student,
            )
        )

    competencies: dict[str, models.Competency] = {}
    indicators: dict[str, models.Indicator] = {}
    for code, kind, description, inds in COMPETENCIES:
        c = models.Competency(code=code, kind=kind, description=description)
        for icode, idesc in inds:
            indicators[icode] = models.Indicator(code=icode, description=idesc)
            c.indicators.append(indicators[icode])
        competencies[code] = c
        session.add(c)

    disciplines = {
        name: models.Discipline(name=name, competencies=[competencies[c] for c in codes])
        for name, codes in DISCIPLINES.items()
    }
    session.add_all(disciplines.values())

    code, name, generals = STANDARD
    standard = models.ProfStandard(code=code, name=name)
    for gcode, gname, level, functions in generals:
        general = models.GeneralLaborFunction(code=gcode, name=gname, qualification_level=level)
        for fcode, fname, ccodes in functions:
            general.functions.append(
                models.LaborFunction(
                    code=fcode, name=fname, competencies=[competencies[c] for c in ccodes]
                )
            )
        standard.general_functions.append(general)
    session.add(standard)

    for icode, discipline, text, options, correct in QUESTIONS:
        indicator = indicators[icode]
        session.add(
            models.Question(
                competency=indicator.competency,
                indicator=indicator,
                discipline=disciplines[discipline],
                text=text,
                options=[
                    models.AnswerOption(text=o, is_correct=i == correct)
                    for i, o in enumerate(options)
                ],
            )
        )
    session.commit()
    print(
        f"добавлено: {len(competencies)} компетенций, {len(QUESTIONS)} вопросов, "
        f"{len(STUDENTS)} студентов\n"
        f"демо-логины: {ADMIN_LOGIN[0]}/{ADMIN_LOGIN[1]}, "
        f"student1..{len(STUDENTS)}/{STUDENT_PASSWORD}"
    )


def main() -> None:
    if settings.is_prod:
        raise SystemExit(
            "демо-данные с известными паролями нельзя загружать в ENVIRONMENT=prod; "
            "создайте администратора: python -m scripts.create_admin <логин>"
        )
    migrate()
    with SessionLocal() as session:
        seed(session)


if __name__ == "__main__":
    main()
