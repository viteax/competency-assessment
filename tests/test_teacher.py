"""Кабинет преподавателя: закреплённые дисциплины, квоты, права на банк вопросов, ФОМ."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.accounts import teacher_login
from tests.helpers import by_code, discipline_id


@pytest.fixture
def teacher(login) -> TestClient:
    """Демо-преподаватель: «Операционные системы» и «Технологии программирования»."""
    return login("teacher", "teacher123")


def disciplines(teacher: TestClient) -> dict[str, dict]:
    response = teacher.get("/teacher/disciplines")
    assert response.status_code == 200, response.text
    return {d["discipline"]: d for d in response.json()}


def test_cabinet_shows_quotas_and_progress(teacher: TestClient):
    mine = disciplines(teacher)
    assert set(mine) == {"Операционные системы", "Технологии программирования"}
    tp = mine["Технологии программирования"]
    progress = {c["code"]: (c["required"], c["done"]) for c in tp["competencies"]}
    assert progress == {"ПК-1": (10, 8), "ПК-2": (15, 12)}
    assert (tp["required"], tp["done"]) == (25, 20)
    assert tp["direction"] == "09.03.04 Программная инженерия"
    assert (tp["first_semester"], tp["last_semester"]) == (3, 4)
    os_ = mine["Операционные системы"]
    assert (os_["required"], os_["done"]) == (20, 20)


def test_done_counts_no_more_than_quota(admin: TestClient, teacher: TestClient):
    entry = next(
        e
        for e in admin.get("/curriculum").json()
        if e["discipline_id"] == discipline_id(admin, "Операционные системы")
    )
    opk5 = by_code(admin, "ОПК-5")["id"]
    updated = admin.put(
        f"/curriculum/{entry['id']}",
        json={**entry, "quotas": [{"competency_id": opk5, "questions": 5}]},
    )
    assert updated.status_code == 200, updated.text
    os_ = disciplines(teacher)["Операционные системы"]
    assert os_["competencies"][0]["done"] == 20
    assert (os_["required"], os_["done"]) == (5, 5)  # лишние вопросы сверх квоты не считаются


def question(competency_id: int, discipline: int | None, text: str = "Новый вопрос") -> dict:
    return {
        "competency_id": competency_id,
        "discipline_id": discipline,
        "text": text,
        "kind": "open",
        "options": [{"text": "ответ"}],
    }


def test_teacher_sees_only_own_questions(admin: TestClient, teacher: TestClient):
    own = {
        discipline_id(admin, "Операционные системы"),
        discipline_id(admin, "Технологии программирования"),
    }
    questions = teacher.get("/questions").json()
    assert questions and {q["discipline_id"] for q in questions} == own
    math = discipline_id(admin, "Математика")
    assert teacher.get("/questions", params={"discipline_id": math}).json() == []


def test_teacher_creates_and_edits_only_within_own_disciplines(admin, teacher):
    tp = discipline_id(admin, "Технологии программирования")
    pk1 = by_code(admin, "ПК-1")["id"]
    created = teacher.post("/questions", json=question(pk1, tp))
    assert created.status_code == 201, created.text
    assert disciplines(teacher)["Технологии программирования"]["done"] == 21

    math = discipline_id(admin, "Математика")
    opk1 = by_code(admin, "ОПК-1")["id"]
    assert teacher.post("/questions", json=question(opk1, math)).status_code == 403
    assert teacher.post("/questions", json=question(pk1, None)).status_code == 403
    # ОПК-1 дисциплина «Технологии программирования» не формирует
    wrong = teacher.post("/questions", json=question(opk1, tp))
    assert wrong.status_code == 400 and "не формирует" in wrong.json()["detail"]

    qid = created.json()["id"]
    moved = teacher.put(f"/questions/{qid}", json=question(opk1, math, "перенос"))
    assert moved.status_code == 403  # перенести в чужую дисциплину нельзя
    foreign = next(q for q in admin.get("/questions").json() if q["discipline_id"] == math)
    assert teacher.delete(f"/questions/{foreign['id']}").status_code == 403
    assert teacher.delete(f"/questions/{qid}").status_code == 204


def test_teacher_has_no_admin_access(teacher: TestClient, student: TestClient):
    for path in ["/tests", "/curriculum", "/users", "/groups", "/reports/groups/1/competencies"]:
        assert teacher.get(path).status_code == 403, path
    assert student.get("/teacher/disciplines").status_code == 403
    assert student.get("/questions").status_code == 403


def test_teacher_downloads_fund_of_own_discipline(admin, teacher):
    tp = discipline_id(admin, "Технологии программирования")
    response = teacher.get(f"/teacher/disciplines/{tp}/fund.docx", params={"key": True})
    assert response.status_code == 200
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
    math = discipline_id(admin, "Математика")
    assert teacher.get(f"/teacher/disciplines/{math}/fund.docx").status_code == 404


def test_admin_assigns_teacher_and_validates_quotas(admin: TestClient, login):
    created = admin.post(
        "/users",
        json={
            "username": "petrov",
            "password": "temp-pass-123",
            "role": "teacher",
            "full_name": "Петров Пётр Петрович",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["full_name"] == "Петров Пётр Петрович"
    nameless = admin.post(
        "/users", json={"username": "x-teacher", "password": "temp-pass-123", "role": "teacher"}
    )
    assert nameless.status_code == 422

    math = discipline_id(admin, "Математика")
    entry = next(e for e in admin.get("/curriculum").json() if e["discipline_id"] == math)
    opk1, pk1 = by_code(admin, "ОПК-1")["id"], by_code(admin, "ПК-1")["id"]
    ok = admin.put(
        f"/curriculum/{entry['id']}",
        json={
            **entry,
            "teacher_id": created.json()["id"],
            "quotas": [{"competency_id": opk1, "questions": 4}],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["quotas"] == [{"competency_id": opk1, "questions": 4}]

    bad = admin.put(
        f"/curriculum/{entry['id']}",
        json={**entry, "quotas": [{"competency_id": pk1, "questions": 4}]},
    )
    assert bad.status_code == 400  # «Математика» не формирует ПК-1
    student_user = next(u for u in admin.get("/users").json() if u["role"] == "student")
    not_teacher = admin.put(
        f"/curriculum/{entry['id']}", json={**entry, "teacher_id": student_user["id"]}
    )
    assert not_teacher.status_code == 400
    twice = admin.put(
        f"/curriculum/{entry['id']}",
        json={
            **entry,
            "quotas": [
                {"competency_id": opk1, "questions": 4},
                {"competency_id": opk1, "questions": 5},
            ],
        },
    )
    assert twice.status_code == 400

    petrov = login("petrov", "temp-pass-123")  # временный пароль – сначала сменить
    assert petrov.get("/teacher/disciplines").status_code == 403
    petrov.post(
        "/me/password",
        json={"current_password": "temp-pass-123", "new_password": "strong-teacher-pass"},
    )
    petrov = login("petrov", "strong-teacher-pass")
    assert [d["discipline"] for d in petrov.get("/teacher/disciplines").json()] == ["Математика"]


def test_second_teacher_with_same_name_is_rejected(admin: TestClient):
    def create(username: str, full_name: str):
        return admin.post(
            "/users",
            json={
                "username": username,
                "password": "Kafedra-2026!",
                "role": "teacher",
                "full_name": full_name,
            },
        )

    assert create("666", "Ботаева Лариса Борисовна").status_code == 201
    # Тот же человек: другой регистр, «ё», порядок слов и лишние пробелы.
    duplicate = create("999", "  лариса  борисовна БОТАЁВА ")
    assert duplicate.status_code == 409
    assert "логин 666" in duplicate.json()["detail"]
    assert create("1000", "Ботаева Лариса Петровна").status_code == 201


def test_teacher_sees_plan_year(admin: TestClient, login):
    plan = admin.post(
        "/directions", json={"code": "11.03.02", "name": "Связь", "plan_year": 2023}
    ).json()
    teacher = admin.post(
        "/users",
        json={
            "username": "plan.teacher",
            "password": "Temp-pass-4821",
            "role": "teacher",
            "full_name": "Планов Пётр Петрович",
        },
    ).json()
    discipline = admin.post(
        "/disciplines", json={"direction_id": plan["id"], "name": "Волокно"}
    ).json()
    entry = admin.post(
        "/curriculum",
        json={
            "direction_id": plan["id"],
            "discipline_id": discipline["id"],
            "first_semester": 1,
            "last_semester": 1,
            "teacher_id": teacher["id"],
        },
    )
    assert entry.status_code == 201, entry.text
    client = login("plan.teacher", "Temp-pass-4821")
    client.post(
        "/me/password",
        json={"current_password": "Temp-pass-4821", "new_password": "Long-new-pass-4821"},
    )
    client = login("plan.teacher", "Long-new-pass-4821")
    [found] = client.get("/teacher/disciplines").json()
    assert found["direction"] == "11.03.02 Связь, 2023"


# --- добавление списком: логин из фамилии и инициалов ------------------------------------------


def _bulk(admin: TestClient, *names: str) -> dict:
    response = admin.post("/users/teachers", json={"full_names": list(names)})
    assert response.status_code == 200, response.text
    return response.json()


def test_teacher_login_is_surname_and_initials():
    assert teacher_login("Ханкишиева Наиля Рамизовна") == "Ханкишиева Н.Р."
    assert teacher_login("  Иванов   Иван ") == "Иванов И."
    assert teacher_login("Иванов") == "Иванов"


def test_bulk_creates_accounts_with_passwords(admin: TestClient):
    result = _bulk(admin, "Сидоров Иван Иванович", "", "   ", "  Петров   Пётр ")
    assert [t["username"] for t in result["created"]] == ["Сидоров И.И.", "Петров П."]
    assert [t["full_name"] for t in result["created"]] == ["Сидоров Иван Иванович", "Петров Пётр"]
    assert all(len(t["password"]) >= 8 for t in result["created"])
    assert result["skipped"] == []


def test_bulk_password_must_be_changed(admin: TestClient):
    _bulk(admin, "Сидоров Иван Иванович")
    users = {u["username"]: u for u in admin.get("/users").json()}
    assert users["Сидоров И.И."]["must_change_password"] is True
    assert users["Сидоров И.И."]["role"] == "teacher"


def test_bulk_skips_duplicates_and_keeps_the_rest(admin: TestClient):
    _bulk(admin, "Сидоров Иван Иванович")
    result = _bulk(admin, "сидоров  иван ИВАНОВИЧ", "Новиков Олег", "Новиков Олег", "Лебедев Ян")
    assert [t["username"] for t in result["created"]] == ["Новиков О.", "Лебедев Я."]
    assert [s["full_name"] for s in result["skipped"]] == ["сидоров иван ИВАНОВИЧ", "Новиков Олег"]
    assert all(s["reason"] for s in result["skipped"])


def test_bulk_namesakes_get_a_number(admin: TestClient):
    result = _bulk(admin, "Иванов Иван Ильич", "Иванов Игорь Ильич", "Иванов Илья Игоревич")
    assert [t["username"] for t in result["created"]] == [
        "Иванов И.И.",
        "Иванов И.И.2",
        "Иванов И.И.3",
    ]


def test_bulk_skips_too_short_name(admin: TestClient):
    result = _bulk(admin, "Ян", "Новиков Олег")
    assert [s["full_name"] for s in result["skipped"]] == ["Ян"]
    assert [t["username"] for t in result["created"]] == ["Новиков О."]


def test_bulk_requires_admin(student: TestClient):
    response = student.post("/users/teachers", json={"full_names": ["Новиков Олег"]})
    assert response.status_code == 403


def test_bulk_limits_list_size(admin: TestClient):
    names = [f"Фамилия{i} Имя" for i in range(201)]
    assert admin.post("/users/teachers", json={"full_names": names}).status_code == 422


@pytest.mark.parametrize(
    "typed",
    ["Ханкишиева Н.Р.", "ханкишиева н.р.", "Ханкишиева Н. Р.", "ханкишиева нр", " Ханкишиева  НР "],
)
def test_teacher_logs_in_with_any_spelling(admin: TestClient, client: TestClient, typed: str):
    [created] = _bulk(admin, "Ханкишиева Наиля Рамизовна")["created"]
    response = client.post("/auth/token", data={"username": typed, "password": created["password"]})
    assert response.status_code == 200, response.text


def test_yo_in_teacher_login(admin: TestClient, client: TestClient):
    [created] = _bulk(admin, "Семёнов Пётр")["created"]
    assert created["username"] == "Семёнов П."
    data = {"username": "семенов п", "password": created["password"]}
    assert client.post("/auth/token", data=data).status_code == 200


def test_login_without_space_stays_exact(admin: TestClient, client: TestClient):
    [created] = _bulk(admin, "Новиков Олег")["created"]
    data = {"username": "новиковО", "password": created["password"]}
    assert client.post("/auth/token", data=data).status_code == 401


def test_slowdown_ignores_spelling_of_teacher_login(admin: TestClient, client: TestClient):
    """Варианты написания логина – один счётчик неудач, перебором написаний паузу не обойти."""
    [created] = _bulk(admin, "Ханкишиева Наиля Рамизовна")["created"]
    spellings = [
        "ханкишиева нр",
        "Ханкишиева Н.Р.",
        "ханкишиева н. р.",
        "ХАНКИШИЕВА Н Р",
        "ханкишиева н.р",
    ]
    assert len(spellings) >= settings.login_slowdown_after
    for spelling in spellings[: settings.login_slowdown_after]:
        data = {"username": spelling, "password": "неверный-пароль"}
        assert client.post("/auth/token", data=data).status_code == 401
    data = {"username": "ханкишиева нр", "password": created["password"]}
    assert client.post("/auth/token", data=data).status_code == 429


def test_login_similar_to_existing_key_gets_a_number(admin: TestClient):
    body = {
        "username": "Иванов ИИ",
        "password": "Temp-pass-4821",
        "role": "teacher",
        "full_name": "Иванов Иван Иннокентьевич",
    }
    assert admin.post("/users", json=body).status_code == 201
    [created] = _bulk(admin, "Иванов Илья Ильич")["created"]
    assert created["username"] == "Иванов И.И.2"


def test_ambiguous_loose_login_finds_nobody(admin: TestClient, client: TestClient):
    """Два логина с одним ключом (завели вручную): угадывать нельзя, точный ввод работает."""
    for username, name in (
        ("Иванов ИИ", "Иванов Иван Ильич"),
        ("Иванов И.И", "Иванов Игорь Ильич"),
    ):
        body = {
            "username": username,
            "password": "Temp-pass-4821",
            "role": "teacher",
            "full_name": name,
        }
        assert admin.post("/users", json=body).status_code == 201
    loose = {"username": "иванов и и", "password": "Temp-pass-4821"}
    assert client.post("/auth/token", data=loose).status_code == 401
    exact = {"username": "Иванов И.И", "password": "Temp-pass-4821"}
    assert client.post("/auth/token", data=exact).status_code == 200
