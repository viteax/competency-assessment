"""Главная страница администратора: цифры, прогресс преподавателей, что требует внимания."""

from fastapi.testclient import TestClient

from tests.helpers import assign


def test_dashboard_on_demo_data(admin: TestClient, student: TestClient):
    ctx = assign(admin, ["ПК-1"])
    started = student.post("/me/attempts", json={"assignment_id": ctx["assignment"]["id"]}).json()
    student.post(f"/me/attempts/{started['attempt_id']}/submit", json={"answers": []})

    data = admin.get("/reports/dashboard").json()
    assert data["counts"] == {
        "groups": 1,
        "students": 3,
        "students_with_account": 3,
        "teachers": 1,
        "questions": 100,
        "tests": 1,
    }
    # Незаконченные дисциплины – первыми.
    assert [(t["discipline"], t["done"], t["required"]) for t in data["teachers"]] == [
        ("Технологии программирования", 20, 25),
        ("Операционные системы", 20, 20),
    ]
    (recent,) = data["assignments"]
    assert (recent["test"], recent["group"], recent["students"], recent["finished"]) == (
        ctx["test"]["title"],
        "ПИ-21",
        3,
        1,
    )
    attention = {a["target"]: a["text"] for a in data["attention"]}
    assert attention["curriculum"].startswith("Не закреплены за преподавателем: Математика")
    assert "students" not in attention  # у всех демо-студентов есть учётки


def test_attention_items(admin: TestClient):
    group = admin.post("/groups", json={"name": "ПИ-25", "direction_id": 1}).json()
    admin.post("/students", json={"full_name": "Новиков Илья Сергеевич", "group_id": group["id"]})
    admin.post("/competencies", json={"code": "ПК-9", "kind": "ПК", "description": "новая"})

    data = admin.get("/reports/dashboard").json()
    attention = {a["target"]: a["text"] for a in data["attention"]}
    assert attention["groups"] == "Не указан год набора (не считается семестр): ПИ-25"
    assert attention["bank"] == "Компетенции без вопросов в банке: ПК-9"
    assert attention["students"].startswith("Студентов без учётной записи: 1.")
    assert "tests" in attention  # тестов ещё нет


def test_dashboard_is_admin_only(student: TestClient):
    assert student.get("/reports/dashboard").status_code == 403
