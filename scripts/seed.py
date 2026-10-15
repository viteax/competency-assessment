"""Заполняет БД демонстрационными данными.

Направление, группа со студентами, несколько компетенций с индикаторами, дисциплины с
семестрами учебного плана, фрагмент профстандарта 06.001 «Программист» и банк вопросов
(по 20 на компетенцию). Формулировки компетенций и вопросов — примерные, для реального УП
их нужно заменить на формулировки из ФГОС/ОПОП.
"""

import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import SessionLocal
from app.demo import DEMO_ADMIN, DEMO_STUDENT_COUNT, DEMO_STUDENT_PASSWORD
from app.models import CompetencyKind as K
from app.security import hash_password
from scripts.demo_questions import QUESTIONS
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

# Дисциплина: (компетенции, первый и последний семестр в учебном плане 09.03.04).
DISCIPLINES = {
    "Математика": (["ОПК-1", "УК-1"], 1, 2),
    "Программирование": (["ПК-1", "УК-1"], 1, 2),
    "Операционные системы": (["ОПК-5"], 3, 3),
    "Технологии программирования": (["ПК-1", "ПК-2"], 3, 4),
    "Тестирование программного обеспечения": (["ПК-2"], 5, 6),
}
# Группа третьего курса: осенью 2026 года — 5-й семестр, и «Тестирование ПО» ещё изучается.
GROUP_START_YEAR = 2024

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
    group = models.Group(name="ПИ-21", direction=direction, start_year=GROUP_START_YEAR)
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
        for name, (codes, _, _) in DISCIPLINES.items()
    }
    session.add_all(disciplines.values())
    session.add_all(
        models.CurriculumEntry(
            direction=direction,
            discipline=disciplines[name],
            first_semester=first,
            last_semester=last,
        )
        for name, (_, first, last) in DISCIPLINES.items()
    )

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

    rng = random.Random(0)  # правильный ответ — на разных местах, но одинаково при каждой загрузке
    for icode, discipline, text, (correct, *wrong) in QUESTIONS:
        indicator = indicators[icode]
        options = [models.AnswerOption(text=correct, is_correct=True)] + [
            models.AnswerOption(text=o) for o in wrong
        ]
        rng.shuffle(options)
        session.add(
            models.Question(
                competency=indicator.competency,
                indicator=indicator,
                discipline=disciplines[discipline],
                text=text,
                options=options,
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
