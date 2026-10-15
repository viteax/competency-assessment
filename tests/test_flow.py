"""Сквозной сценарий с наброска: админ назначает группе тест по компетенциям,
студент проходит его, по результатам строятся отчёты по компетенциям и ТФ профстандарта."""

from fastapi.testclient import TestClient

from tests.helpers import assign, by_code, correct_answers, discipline_id, student_id


def test_full_flow(admin: TestClient, student: TestClient):
    ctx = assign(admin, ["ПК-1", "ПК-2"])

    [pending] = student.get("/me/assignments").json()
    assert (pending["id"], pending["question_count"], pending["attempt"]) == (
        ctx["assignment"]["id"],
        6,
        None,
    )

    started = student.post("/me/attempts", json={"assignment_id": ctx["assignment"]["id"]})
    assert started.status_code == 201, started.text
    body = started.json()
    assert len(body["questions"]) == 6
    # Студент не видит правильные ответы.
    assert all("is_correct" not in o for q in body["questions"] for o in q["options"])

    correct = correct_answers(admin)
    result = student.post(
        f"/me/attempts/{body['attempt_id']}/submit",
        json={"answers": [{"question_id": q["id"], **correct[q["id"]]} for q in body["questions"]]},
    )
    assert result.status_code == 200, result.text
    assert (result.json()["score"], result.json()["max_score"]) == (6, 6)
    [done] = student.get("/me/assignments").json()
    assert (done["attempt"]["score"], done["attempt"]["max_score"]) == (6, 6)

    report = student.get("/me/reports/competencies").json()
    assert {
        (c["code"], c["correct"], c["total"], c["mastered"]) for c in report["competencies"]
    } == {("ПК-1", 3, 3, True), ("ПК-2", 3, 3, True)}
    # Админ видит тот же отчёт.
    assert admin.get(f"/reports/students/{student_id(admin)}/competencies").json() == report

    otf = {g["code"]: g for g in student.get("/me/reports/labor-functions").json()}
    tf = {f["code"]: f["covered"] for g in otf.values() for f in g["functions"]}
    assert tf["A/02.3"] is True  # нужен только ПК-1
    assert tf["A/01.3"] is False  # нужен ещё ОПК-1, его не тестировали
    assert tf["B/03.4"] is False  # нужен ещё ОПК-5
    assert otf["A"]["covered"] is False

    group_report = admin.get(f"/reports/groups/{ctx['group']['id']}/competencies").json()
    assert len(group_report["students"]) == 3


def test_wrong_answers_not_mastered(admin: TestClient, student: TestClient):
    ctx = assign(admin, ["ОПК-5"])
    started = student.post("/me/attempts", json={"assignment_id": ctx["assignment"]["id"]}).json()
    first = started["questions"][0]
    # Отвечаем верно только на первый вопрос, остальные пропускаем.
    result = student.post(
        f"/me/attempts/{started['attempt_id']}/submit",
        json={"answers": [{"question_id": first["id"], **correct_answers(admin)[first["id"]]}]},
    ).json()
    assert (result["score"], result["max_score"]) == (1, 3)

    [opk5] = student.get("/me/reports/competencies").json()["competencies"]
    assert opk5["mastered"] is False and opk5["ratio"] == 0.333


def test_test_spreads_questions_across_indicators(admin: TestClient):
    opk1 = by_code(admin, "ОПК-1")
    test = admin.post(
        "/tests",
        json={
            "title": "t",
            "competency_ids": [opk1["id"]],
            "questions_per_competency": 2,
            "discipline_ids": [discipline_id(admin, "Математика")],
        },
    ).json()
    questions = {q["id"]: q for q in admin.get("/questions").json()}
    assert {questions[q]["indicator_id"] for q in test["question_ids"]} == {
        i["id"] for i in opk1["indicators"]
    }
