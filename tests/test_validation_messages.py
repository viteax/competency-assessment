"""Ошибки проверки запроса (422) – по-русски и без эха введённых значений."""

from fastapi.testclient import TestClient

from tests.helpers import by_code


def messages(response) -> list[str]:
    assert response.status_code == 422
    return [e["msg"] for e in response.json()["detail"]]


def test_missing_and_empty_fields(admin: TestClient):
    response = admin.post("/questions", json={"text": "", "kind": "open", "options": []})
    assert messages(response) == [
        "Компетенция: обязательное поле",
        "Текст: не заполнено",
        "Варианты: нужен хотя бы один элемент",
    ]


def test_numbers_and_choices(admin: TestClient):
    pk1 = by_code(admin, "ПК-1")["id"]
    response = admin.post(
        "/tests",
        json={"title": "t", "competency_ids": [pk1], "questions_per_competency": 0},
    )
    assert messages(response) == ["Вопросов на компетенцию: не меньше 1"]
    response = admin.post(
        "/questions",
        json={"competency_id": "x", "text": "t", "kind": "что-то", "options": [{"text": "a"}]},
    )
    assert messages(response) == [
        "Компетенция: нужно целое число",
        "Тип задания: допустимые значения: 'matching', 'sequence', 'open'",
    ]


def test_model_checks_keep_own_wording(admin: TestClient):
    response = admin.post(
        "/questions",
        json={
            "competency_id": by_code(admin, "ПК-1")["id"],
            "text": "t",
            "kind": "sequence",
            "options": [{"text": "a"}],
        },
    )
    assert messages(response) == ["в последовательности нужно не меньше двух элементов"]


def test_entered_values_are_not_echoed(client: TestClient):
    response = client.post(
        "/auth/register", json={"group_id": "x", "full_name": "Иванов", "password": "секрет-123"}
    )
    assert "секрет-123" not in response.text
    assert messages(response) == ["Группа: нужно целое число"]
