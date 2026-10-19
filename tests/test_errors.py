from fastapi.testclient import TestClient

from tests.helpers import assign, by_code


def test_not_enough_questions(admin: TestClient):
    response = admin.post(
        "/tests",
        json={
            "title": "t",
            "competency_ids": [by_code(admin, "УК-1")["id"]],
            "questions_per_competency": 21,  # в демо-банке 20
        },
    )
    assert response.status_code == 400
    assert "УК-1 — 20 из 21" in response.json()["detail"]


def test_unknown_competency(admin: TestClient):
    response = admin.post("/tests", json={"title": "t", "competency_ids": [999]})
    assert response.status_code == 404


def test_duplicate_assignment(admin: TestClient):
    ctx = assign(admin, ["ПК-1"])
    again = admin.post(
        "/assignments", json={"test_id": ctx["test"]["id"], "group_id": ctx["group"]["id"]}
    )
    assert again.status_code == 409


def test_student_from_other_group_cannot_start(admin: TestClient, login):
    ctx = assign(admin, ["ПК-1"])
    other_group = admin.post(
        "/groups", json={"name": "ПИ-22", "direction_id": ctx["group"]["direction_id"]}
    ).json()
    stranger = admin.post("/students", json={"full_name": "Чужой", "group_id": other_group["id"]})
    admin.post(
        "/users",
        json={
            "username": "stranger",
            "password": "secret12",
            "role": "student",
            "student_id": stranger.json()["id"],
        },
    )
    client = login("stranger", "secret12")
    change = {"current_password": "secret12", "new_password": "other-group-pw"}
    client.post("/me/password", json=change, headers={"X-Requested-With": "fetch"})
    client = login("stranger", "other-group-pw")
    assert client.get("/me/assignments").json() == []
    response = client.post("/me/attempts", json={"assignment_id": ctx["assignment"]["id"]})
    assert response.status_code == 404


def test_cannot_submit_twice_or_restart(admin: TestClient, student: TestClient):
    ctx = assign(admin, ["ПК-1"])
    payload = {"assignment_id": ctx["assignment"]["id"]}
    attempt_id = student.post("/me/attempts", json=payload).json()["attempt_id"]
    # Повторный старт до сдачи возвращает ту же попытку.
    assert student.post("/me/attempts", json=payload).json()["attempt_id"] == attempt_id

    submit = f"/me/attempts/{attempt_id}/submit"
    assert student.post(submit, json={"answers": []}).status_code == 200
    assert student.post(submit, json={"answers": []}).status_code == 409
    assert student.post("/me/attempts", json=payload).status_code == 409


def test_cannot_submit_someone_elses_attempt(admin: TestClient, student: TestClient, login):
    ctx = assign(admin, ["ПК-1"])
    attempt_id = student.post(
        "/me/attempts", json={"assignment_id": ctx["assignment"]["id"]}
    ).json()["attempt_id"]
    classmate = login("student2", "student123")
    response = classmate.post(f"/me/attempts/{attempt_id}/submit", json={"answers": []})
    assert response.status_code == 404


def test_option_from_another_question(admin: TestClient, student: TestClient):
    ctx = assign(admin, ["ПК-1"], per_competency=19)  # все задания ПК-1, в т.ч. на соответствие
    started = student.post("/me/attempts", json={"assignment_id": ctx["assignment"]["id"]}).json()
    q1 = next(q for q in started["questions"] if q["kind"] == "matching")
    foreign = next(
        o["id"]
        for q in admin.get("/questions").json()
        if q["kind"] == "matching" and q["id"] != q1["id"]
        for o in q["options"]
    )
    response = student.post(
        f"/me/attempts/{started['attempt_id']}/submit",
        json={"answers": [{"question_id": q1["id"], "pairs": {q1["options"][0]["id"]: foreign}}]},
    )
    assert response.status_code == 400


def test_single_choice_is_not_accepted(admin: TestClient):
    """Кафедра использует три типа заданий: соответствие, последовательность, открытый."""
    response = admin.post(
        "/questions",
        json={
            "competency_id": by_code(admin, "ПК-1")["id"],
            "text": "?",
            "kind": "single",
            "options": [{"text": "a"}, {"text": "b"}],
        },
    )
    assert response.status_code == 422


def test_indicator_must_belong_to_competency(admin: TestClient):
    pk1, pk2 = by_code(admin, "ПК-1"), by_code(admin, "ПК-2")
    response = admin.post(
        "/questions",
        json={
            "competency_id": pk1["id"],
            "indicator_id": pk2["indicators"][0]["id"],
            "text": "?",
            "kind": "open",
            "options": [{"text": "a"}],
        },
    )
    assert response.status_code == 400


def test_duplicate_competency_code(admin: TestClient):
    response = admin.post(
        "/competencies", json={"code": "ПК-1", "kind": "ПК", "description": "дубль"}
    )
    assert response.status_code == 409


def test_test_title_is_unique(admin: TestClient):
    pk1 = by_code(admin, "ПК-1")["id"]
    body = {"competency_ids": [pk1], "questions_per_competency": 2}
    assert admin.post("/tests", json={**body, "title": "Входной контроль"}).status_code == 201
    for duplicate in ["Входной контроль", "  входной   КОНТРОЛЬ "]:
        response = admin.post("/tests", json={**body, "title": duplicate})
        assert response.status_code == 409
        assert "уже есть" in response.json()["detail"]
    assert admin.post("/tests", json={**body, "title": "   "}).status_code == 422
    assert admin.post("/tests", json={**body, "title": "Входной контроль 2"}).status_code == 201


def test_existing_test_can_be_assigned_to_another_group(admin: TestClient):
    ctx = assign(admin, ["ПК-1"])
    other = admin.post(
        "/groups", json={"name": "ПИ-22", "direction_id": ctx["group"]["direction_id"]}
    ).json()
    response = admin.post(
        "/assignments", json={"test_id": ctx["test"]["id"], "group_id": other["id"]}
    )
    assert response.status_code == 201
    [listed] = admin.get("/tests").json()
    assert (listed["title"], sorted(listed["group_ids"])) == (
        "Входной контроль",
        sorted([ctx["group"]["id"], other["id"]]),
    )
