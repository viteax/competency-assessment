from fastapi.testclient import TestClient

from tests.helpers import by_code, correct_options
from tests.test_flow import setup_assignment


def test_not_enough_questions(client: TestClient):
    response = client.post(
        "/tests",
        json={
            "title": "t",
            "competency_ids": [by_code(client, "УК-1")["id"]],
            "questions_per_competency": 5,
        },
    )
    assert response.status_code == 400
    assert "УК-1" in response.json()["detail"]


def test_unknown_competency(client: TestClient):
    response = client.post("/tests", json={"title": "t", "competency_ids": [999]})
    assert response.status_code == 404


def test_duplicate_assignment(client: TestClient):
    ctx = setup_assignment(client, ["ПК-1"])
    again = client.post(
        "/assignments", json={"test_id": ctx["test"]["id"], "group_id": ctx["group"]["id"]}
    )
    assert again.status_code == 409


def test_student_from_other_group(client: TestClient):
    ctx = setup_assignment(client, ["ПК-1"])
    other_group = client.post(
        "/groups", json={"name": "ПИ-22", "direction_id": ctx["group"]["direction_id"]}
    ).json()
    stranger = client.post("/students", json={"full_name": "Чужой", "group_id": other_group["id"]})
    response = client.post(
        "/attempts",
        json={"assignment_id": ctx["assignment"]["id"], "student_id": stranger.json()["id"]},
    )
    assert response.status_code == 400


def test_cannot_submit_twice_or_restart(client: TestClient):
    ctx = setup_assignment(client, ["ПК-1"])
    payload = {"assignment_id": ctx["assignment"]["id"], "student_id": ctx["student"]["id"]}
    attempt_id = client.post("/attempts", json=payload).json()["attempt_id"]
    # Повторный старт до сдачи возвращает ту же попытку.
    assert client.post("/attempts", json=payload).json()["attempt_id"] == attempt_id

    assert client.post(f"/attempts/{attempt_id}/submit", json={"answers": []}).status_code == 200
    assert client.post(f"/attempts/{attempt_id}/submit", json={"answers": []}).status_code == 409
    assert client.post("/attempts", json=payload).status_code == 409


def test_option_from_another_question(client: TestClient):
    ctx = setup_assignment(client, ["ПК-1"])
    started = client.post(
        "/attempts",
        json={"assignment_id": ctx["assignment"]["id"], "student_id": ctx["student"]["id"]},
    ).json()
    q1, q2 = started["questions"][:2]
    response = client.post(
        f"/attempts/{started['attempt_id']}/submit",
        json={
            "answers": [{"question_id": q1["id"], "option_id": correct_options(client)[q2["id"]]}]
        },
    )
    assert response.status_code == 400


def test_question_needs_exactly_one_correct_option(client: TestClient):
    response = client.post(
        "/questions",
        json={
            "competency_id": by_code(client, "ПК-1")["id"],
            "text": "?",
            "options": [{"text": "a", "is_correct": True}, {"text": "b", "is_correct": True}],
        },
    )
    assert response.status_code == 422


def test_indicator_must_belong_to_competency(client: TestClient):
    pk1, pk2 = by_code(client, "ПК-1"), by_code(client, "ПК-2")
    response = client.post(
        "/questions",
        json={
            "competency_id": pk1["id"],
            "indicator_id": pk2["indicators"][0]["id"],
            "text": "?",
            "options": [{"text": "a", "is_correct": True}, {"text": "b"}],
        },
    )
    assert response.status_code == 400


def test_duplicate_competency_code(client: TestClient):
    response = client.post(
        "/competencies", json={"code": "ПК-1", "kind": "ПК", "description": "дубль"}
    )
    assert response.status_code == 409
