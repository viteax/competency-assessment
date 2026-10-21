"""Черновик ответов: сохраняется по ходу теста, возвращается при повторном открытии,
стирается при сдаче и не влияет на оценку."""

from fastapi.testclient import TestClient

from tests.helpers import assign, correct_answers


def _start(admin: TestClient, student: TestClient) -> dict:
    # Все задания ПК-2 – в тесте точно есть все три типа.
    ctx = assign(admin, ["ПК-2"], per_competency=20)
    started = student.post("/me/attempts", json={"assignment_id": ctx["assignment"]["id"]})
    return {**started.json(), "assignment_id": ctx["assignment"]["id"]}


def _by_kind(started: dict, kind: str) -> dict:
    return next(q for q in started["questions"] if q["kind"] == kind)


def test_draft_comes_back_and_is_cleared_on_submit(admin: TestClient, student: TestClient):
    started = _start(admin, student)
    assert started["draft"] == []
    matching = _by_kind(started, "matching")
    left = matching["options"][0]["id"]
    # Неполный ответ на соответствие: выбрана пара только для одного элемента.
    draft = [{"question_id": matching["id"], "pairs": {str(left): matching["right"][0]["id"]}}]
    url = f"/me/attempts/{started['attempt_id']}/draft"
    assert student.put(url, json={"answers": draft}).status_code == 204

    again = student.post("/me/attempts", json={"assignment_id": started["assignment_id"]})
    assert again.json()["draft"] == [{**draft[0], "text": None, "order": None}]

    correct = correct_answers(admin)
    result = student.post(
        f"/me/attempts/{started['attempt_id']}/submit",
        json={
            "answers": [{"question_id": q["id"], **correct[q["id"]]} for q in started["questions"]]
        },
    ).json()
    assert result["score"] == result["max_score"]  # черновик на оценку не влияет
    assert student.put(url, json={"answers": draft}).status_code == 409


def test_draft_rejects_foreign_elements(admin: TestClient, student: TestClient):
    started = _start(admin, student)
    url = f"/me/attempts/{started['attempt_id']}/draft"
    sequence = _by_kind(started, "sequence")
    ids = [o["id"] for o in sequence["options"]]

    foreign = student.put(
        url, json={"answers": [{"question_id": sequence["id"], "order": [10**6]}]}
    )
    assert foreign.status_code == 400, foreign.text
    padded = student.put(
        url, json={"answers": [{"question_id": sequence["id"], "order": ids * 50}]}
    )
    assert padded.status_code == 400, padded.text
    unknown = student.put(url, json={"answers": [{"question_id": 10**6, "text": "x"}]})
    assert unknown.status_code == 404


def test_draft_of_another_student_is_not_found(admin: TestClient, student: TestClient, login):
    started = _start(admin, student)
    other = login("student2", "student123")
    response = other.put(f"/me/attempts/{started['attempt_id']}/draft", json={"answers": []})
    assert response.status_code == 404
