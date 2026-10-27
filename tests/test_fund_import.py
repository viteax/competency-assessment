"""Загрузка вопросов из ФОС дисциплины (Word или .zip с несколькими документами)."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.services import fund_import
from tests.helpers import discipline_id
from tests.import_samples import fund_docx, rpd_docx

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_parse_reads_tasks_answers_and_levels():
    doc = fund_import.parse("ФОС.docx", fund_docx())
    assert (doc.direction_code, doc.discipline, doc.semester, doc.error) == (
        "09.03.04",
        "Архитектура ПО",
        3,
        None,
    )
    assert doc.competencies == {
        "ПК-1": "Способен разрабатывать программы",
        "ПК-7": "Способен проектировать архитектуру программного обеспечения",
    }
    tasks = [(t.competency, t.number, t.kind.value, t.difficulty.value, t.error) for t in doc.tasks]
    assert tasks == [
        ("ПК-1", 1, "matching", "advanced", None),
        ("ПК-1", 2, "sequence", "basic", None),
        ("ПК-1", 3, "open", "basic", None),
        ("ПК-7", 1, "open", "advanced", None),
        ("ПК-7", 2, "open", "basic", "нет ответа"),  # бланк: «Ответ: ______.»
    ]
    matching, sequence, inline, listed, _ = doc.tasks
    # Соответствие: подпункты маркерами – часть элемента, лишний элемент правого столбца остается.
    options = matching.options
    pairs = {o.text: options[o.match_index].text for o in options if o.match_index is not None}
    assert pairs == {
        "Класс": "Шаблон для создания объектов.",
        "Объект": "Экземпляр класса, у которого: есть состояние; есть поведение.",
        "Метод": "Функция, объявленная в классе.",
    }
    assert len(options) == 7
    # Последовательность с автонумерацией: варианты – в правильном порядке.
    assert [o.text for o in sequence.options] == [
        "Анализ требований",
        "Проектирование",
        "Реализация",
        "Тестирование",
    ]
    # Ответ в конце абзаца задания и несколько допустимых ответов через « / ».
    assert inline.text == "Шаблон, который гарантирует единственный экземпляр класса, – ______."
    assert [o.text for o in inline.options] == ["одиночка"]
    assert listed.text == "Требования ______ включают:\n– надежность;\n– масштабируемость."
    assert [o.text for o in listed.options] == ["нефункциональные", "нефункциональными"]


def test_round_trip_of_exported_fund(admin: TestClient):
    """ФОМ с ответами, выгруженный из банка, загружается обратно без потерь – и весь
    оказывается уже в банке."""
    disc = discipline_id(admin, "Технологии программирования")
    exported = admin.get(f"/disciplines/{disc}/fund.docx", params={"key": "true"}).content
    doc = fund_import.parse("фом.docx", exported)
    bank = admin.get("/questions", params={"discipline_id": disc}).json()
    assert [t.error for t in doc.tasks] == [None] * len(bank)
    codes = {c["id"]: c["code"] for c in admin.get("/competencies").json()}

    def canonical(competency, kind, difficulty, text, pairs, items):
        return (competency, kind, difficulty, text, sorted(pairs), items)

    expected = []
    for q in bank:
        by_id = {o["id"]: o["text"] for o in q["options"]}
        pairs = [(o["text"], by_id[o["match_id"]]) for o in q["options"] if o["match_id"]]
        items = [o["text"] for o in q["options"] if not o["match_id"]]
        if q["kind"] == "matching":
            items = sorted(set(items) - {r for _, r in pairs})  # лишние элементы правого столбца
        args = (codes[q["competency_id"]], q["kind"], q["difficulty"], q["text"], pairs, items)
        expected.append(canonical(*args))
    got = []
    for t in doc.tasks:
        options = t.options
        pairs = [
            (o.text, options[o.match_index].text) for o in options if o.match_index is not None
        ]
        items = [o.text for o in options if o.match_index is None]
        if t.kind.value == "matching":
            items = sorted(set(items) - {r for _, r in pairs})
        got.append(canonical(t.competency, t.kind.value, t.difficulty.value, t.text, pairs, items))
    # Порядок последовательности и допустимые ответы – как в банке, пары соответствия – тоже.
    assert sorted(got) == sorted(expected)

    preview = admin.post(
        "/questions/import/preview", files={"file": ("фом.docx", exported, DOCX)}
    ).json()
    assert {q["status"] for q in preview["documents"][0]["questions"]} == {"duplicate"}


def upload(client: TestClient, path: str, data: bytes, name: str = "ФОС.docx", **form):
    return client.post(path, files={"file": (name, data, DOCX)}, data=form)


def test_new_discipline_and_competency_from_fund(admin: TestClient):
    preview = upload(admin, "/questions/import/preview", fund_docx()).json()
    (doc,) = preview["documents"]
    assert (doc["discipline"], doc["discipline_exists"], doc["error"]) == (
        "Архитектура ПО",
        False,
        None,
    )
    assert [(c["code"], c["exists"]) for c in doc["competencies"]] == [
        ("ПК-1", True),
        ("ПК-7", False),
    ]
    assert [q["status"] for q in doc["questions"]] == ["new", "new", "new", "new", "error"]
    assert doc["questions"][0]["answer"][0] == "Класс → Шаблон для создания объектов."

    result = upload(admin, "/questions/import/apply", fund_docx()).json()
    assert result == {
        "created_questions": 4,
        "duplicates": 0,
        "errors": 1,
        "created_disciplines": 1,
        "created_competencies": 1,
        "directions": ["09.03.04"],
    }
    disc = discipline_id(admin, "Архитектура ПО")
    codes = {c["id"]: c["code"] for c in admin.get("/competencies").json()}
    discipline = next(d for d in admin.get("/disciplines").json() if d["id"] == disc)
    assert sorted(codes[i] for i in discipline["competency_ids"]) == ["ПК-1", "ПК-7"]
    questions = admin.get("/questions", params={"discipline_id": disc}).json()
    assert [(q["kind"], q["difficulty"]) for q in questions] == [
        ("matching", "advanced"),
        ("sequence", "basic"),
        ("open", "basic"),
        ("open", "advanced"),
    ]
    pk7 = next(c for c in admin.get("/competencies").json() if c["code"] == "ПК-7")
    assert pk7["description"] == "Способен проектировать архитектуру программного обеспечения"

    # Повторная загрузка не дублирует вопросы.
    again = upload(admin, "/questions/import/apply", fund_docx()).json()
    assert (again["created_questions"], again["duplicates"], again["errors"]) == (0, 4, 1)


def test_archive_with_several_documents(admin: TestClient):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("1 семестр/Архитектура.docx", fund_docx())
        archive.writestr("1 семестр/Паттерны.docx", fund_docx(discipline="Паттерны"))
        archive.writestr("1 семестр/сломан.docx", b"not a zip")
        archive.writestr("1 семестр/РПД.docx", rpd_docx())
        archive.writestr("1 семестр/заметки.txt", "не документ")
    data = buffer.getvalue()
    preview = upload(admin, "/questions/import/preview", data, name="1 семестр.zip").json()
    errors = {d["filename"]: d["error"] for d in preview["documents"]}
    assert list(errors) == ["Архитектура.docx", "Паттерны.docx", "РПД.docx", "сломан.docx"]
    assert errors["Архитектура.docx"] is None and errors["Паттерны.docx"] is None
    assert "это не ФОС дисциплины" in errors["РПД.docx"]
    assert errors["сломан.docx"].startswith("не удалось прочитать файл")

    result = upload(admin, "/questions/import/apply", data, name="1 семестр.zip").json()
    assert (result["created_questions"], result["created_disciplines"]) == (8, 2)


def test_document_of_unknown_direction(admin: TestClient):
    data = fund_docx(direction="15.04.06 Мехатроника и робототехника")
    (doc,) = upload(admin, "/questions/import/preview", data).json()["documents"]
    assert doc["error"].startswith("направление 15.04.06 не найдено")
    assert {q["status"] for q in doc["questions"]} == {"error"}
    result = upload(admin, "/questions/import/apply", data).json()
    assert (result["created_questions"], result["errors"]) == (0, 5)


def test_teacher_loads_into_own_discipline(login, admin: TestClient):
    teacher = login("teacher", "teacher123")
    own = discipline_id(admin, "Технологии программирования")  # формирует ПК-1 и ПК-2
    assert upload(teacher, "/questions/import/preview", fund_docx()).status_code == 403
    foreign = discipline_id(admin, "Математика")
    response = upload(teacher, "/questions/import/preview", fund_docx(), discipline_id=foreign)
    assert response.status_code == 404

    preview = upload(teacher, "/questions/import/preview", fund_docx(), discipline_id=own).json()
    statuses = [
        (q["competency"], q["status"], q["error"]) for q in preview["documents"][0]["questions"]
    ]
    assert statuses == [
        ("ПК-1", "new", None),
        ("ПК-1", "new", None),
        ("ПК-1", "new", None),
        ("ПК-7", "error", "ПК-7 нет в направлении"),  # преподаватель компетенции не добавляет
        ("ПК-7", "error", "нет ответа"),
    ]
    result = upload(teacher, "/questions/import/apply", fund_docx(), discipline_id=own).json()
    assert (result["created_questions"], result["created_competencies"]) == (3, 0)
    assert len(teacher.get("/questions", params={"discipline_id": own}).json()) == len(
        admin.get("/questions", params={"discipline_id": own}).json()
    )


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("ФОС.doc", b"\xd0\xcf", ".docx"),
        ("архив.zip", b"not a zip", "не удалось прочитать файл"),
    ],
)
def test_wrong_files(admin: TestClient, name: str, data: bytes, message: str):
    response = upload(admin, "/questions/import/preview", data, name=name)
    assert response.status_code == 400 and message in response.json()["detail"]


def test_zip_without_documents(admin: TestClient):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "x")
    response = upload(admin, "/questions/import/preview", buffer.getvalue(), name="a.zip")
    assert response.status_code == 400 and "нет файлов .docx" in response.json()["detail"]


def test_same_wording_with_other_answers_is_not_a_duplicate(admin: TestClient):
    upload(admin, "/questions/import/apply", fund_docx())
    disc = discipline_id(admin, "Архитектура ПО")
    matching = next(
        q
        for q in admin.get("/questions", params={"discipline_id": disc}).json()
        if q["kind"] == "matching"
    )
    # Тот же текст «Соотнесите понятия с определениями:», но другие пары.
    admin.delete(f"/questions/{matching['id']}")
    created = admin.post(
        "/questions",
        json={
            "competency_id": matching["competency_id"],
            "discipline_id": disc,
            "text": matching["text"],
            "kind": "matching",
            "options": [
                {"text": "Интерфейс", "match_index": 2},
                {"text": "Наследование", "match_index": 3},
                {"text": "Контракт без реализации"},
                {"text": "Получение свойств родителя"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    (doc,) = upload(admin, "/questions/import/preview", fund_docx()).json()["documents"]
    assert [q["status"] for q in doc["questions"]] == [
        "new",
        "duplicate",
        "duplicate",
        "duplicate",
        "error",
    ]
