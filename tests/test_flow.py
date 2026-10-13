"""Сквозной сценарий с наброска: админ назначает группе тест по компетенциям,
студент проходит его, по результатам строятся отчёты по компетенциям и ТФ профстандарта."""

from fastapi.testclient import TestClient

from tests.helpers import by_code, correct_options, discipline_id


def setup_assignment(client: TestClient, codes: list[str], per_competency: int = 3) -> dict:
    test = client.post(
        "/tests",
        json={
            "title": "Входной контроль",
            "competency_ids": [by_code(client, c)["id"] for c in codes],
            "questions_per_competency": per_competency,
        },
    )
    assert test.status_code == 201, test.text
    group = client.get("/groups").json()[0]
    assignment = client.post(
        "/assignments", json={"test_id": test.json()["id"], "group_id": group["id"]}
    )
    assert assignment.status_code == 201, assignment.text
    student = client.get("/students", params={"group_id": group["id"]}).json()[0]
    return {
        "test": test.json(),
        "assignment": assignment.json(),
        "student": student,
        "group": group,
    }


def test_full_flow(client: TestClient):
    ctx = setup_assignment(client, ["ПК-1", "ПК-2"])
    student = ctx["student"]

    assert [a["id"] for a in client.get(f"/students/{student['id']}/assignments").json()] == [
        ctx["assignment"]["id"]
    ]

    started = client.post(
        "/attempts", json={"assignment_id": ctx["assignment"]["id"], "student_id": student["id"]}
    )
    assert started.status_code == 201, started.text
    body = started.json()
    assert len(body["questions"]) == 6
    # Студент не видит правильные ответы.
    assert all("is_correct" not in o for q in body["questions"] for o in q["options"])

    correct = correct_options(client)
    result = client.post(
        f"/attempts/{body['attempt_id']}/submit",
        json={
            "answers": [
                {"question_id": q["id"], "option_id": correct[q["id"]]} for q in body["questions"]
            ]
        },
    )
    assert result.status_code == 200, result.text
    assert (result.json()["score"], result.json()["max_score"]) == (6, 6)

    report = client.get(f"/reports/students/{student['id']}/competencies").json()
    assert {
        (c["code"], c["correct"], c["total"], c["mastered"]) for c in report["competencies"]
    } == {
        ("ПК-1", 3, 3, True),
        ("ПК-2", 3, 3, True),
    }

    otf = {
        g["code"]: g
        for g in client.get(f"/reports/students/{student['id']}/labor-functions").json()
    }
    tf = {f["code"]: f["covered"] for g in otf.values() for f in g["functions"]}
    assert tf["A/02.3"] is True  # нужен только ПК-1
    assert tf["A/01.3"] is False  # нужен ещё ОПК-1, его не тестировали
    assert tf["B/03.4"] is False  # нужен ещё ОПК-5
    assert otf["A"]["covered"] is False

    group_report = client.get(f"/reports/groups/{ctx['group']['id']}/competencies").json()
    assert len(group_report["students"]) == 3


def test_wrong_answers_not_mastered(client: TestClient):
    ctx = setup_assignment(client, ["ОПК-5"])
    started = client.post(
        "/attempts",
        json={"assignment_id": ctx["assignment"]["id"], "student_id": ctx["student"]["id"]},
    ).json()
    correct = correct_options(client)
    first = started["questions"][0]
    # Отвечаем верно только на первый вопрос, остальные пропускаем.
    result = client.post(
        f"/attempts/{started['attempt_id']}/submit",
        json={"answers": [{"question_id": first["id"], "option_id": correct[first["id"]]}]},
    ).json()
    assert (result["score"], result["max_score"]) == (1, 3)

    [opk5] = client.get(f"/reports/students/{ctx['student']['id']}/competencies").json()[
        "competencies"
    ]
    assert opk5["mastered"] is False and opk5["ratio"] == 0.333


def test_test_spreads_questions_across_indicators(client: TestClient):
    opk1 = by_code(client, "ОПК-1")
    test = client.post(
        "/tests",
        json={
            "title": "t",
            "competency_ids": [opk1["id"]],
            "questions_per_competency": 2,
            "discipline_id": discipline_id(client, "Математика"),
        },
    ).json()
    questions = {q["id"]: q for q in client.get("/questions").json()}
    assert {questions[q]["indicator_id"] for q in test["question_ids"]} == {
        i["id"] for i in opk1["indicators"]
    }
