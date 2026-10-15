"""Оценка остаточных знаний: дисциплины по семестрам, варианты теста, управление тестами."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.semesters import current_semester
from tests.helpers import assign, by_code, correct_answers, discipline_id


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2024, 9, 1), 1),
        (date(2025, 1, 20), 1),  # сессия осеннего семестра
        (date(2025, 2, 10), 2),
        (date(2025, 7, 1), 2),  # лето: только что завершился 2-й
        (date(2025, 9, 1), 3),
        (date(2026, 10, 15), 5),
        (date(2023, 5, 1), 1),  # до набора — не меньше первого
    ],
)
def test_current_semester(today: date, expected: int):
    assert current_semester(2024, today) == expected


def group(admin: TestClient) -> dict:
    return next(g for g in admin.get("/groups").json() if g["name"] == "ПИ-21")


def plan(admin: TestClient, semester: int | None = None) -> dict:
    params = {"group_id": group(admin)["id"]} | ({"semester": semester} if semester else {})
    response = admin.get("/tests/plan", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_plan_shows_only_disciplines_finished_before_semester(admin: TestClient):
    # Математика и программирование — 1–2 семестры: во 2-м их ещё изучают.
    assert plan(admin, 2)["finished"] == []
    third = plan(admin, 3)
    assert [d["name"] for d in third["finished"]] == ["Математика", "Программирование"]
    fifth = plan(admin, 5)
    assert {d["name"] for d in fifth["finished"]} == {
        "Математика",
        "Программирование",
        "Операционные системы",
        "Технологии программирования",
    }
    assert [d["name"] for d in fifth["not_finished"]] == ["Тестирование программного обеспечения"]
    counts = {
        (c["competency_id"], c["discipline_id"]): c["count"] for c in fifth["question_counts"]
    }
    pk2 = by_code(admin, "ПК-2")["id"]
    assert counts[(pk2, discipline_id(admin, "Технологии программирования"))] == 12
    assert (pk2, discipline_id(admin, "Тестирование программного обеспечения")) not in counts


def test_plan_defaults_to_current_semester(admin: TestClient):
    g = group(admin)
    assert plan(admin)["semester"] == g["current_semester"] == current_semester(2024)


def test_plan_needs_start_year_or_semester(admin: TestClient):
    g = group(admin)
    admin.put(f"/groups/{g['id']}", json={**g, "start_year": None})
    response = admin.get("/tests/plan", params={"group_id": g["id"]})
    assert response.status_code == 400
    assert "год набора" in response.json()["detail"]
    assert admin.get("/tests/plan", params={"group_id": g["id"], "semester": 3}).status_code == 200


def test_disciplines_without_semesters_are_reported(admin: TestClient):
    admin.post("/disciplines", json={"name": "Философия", "competency_ids": []})
    assert plan(admin, 3)["unplanned"] == ["Философия"]


def create(admin: TestClient, codes: list[str], k: int = 5, disciplines=(), **extra):
    return admin.post(
        "/tests",
        json={
            "title": "Остаточные знания",
            "competency_ids": [by_code(admin, c)["id"] for c in codes],
            "questions_per_competency": k,
            "discipline_ids": [discipline_id(admin, d) for d in disciplines],
            **extra,
        },
    )


def test_variants_do_not_overlap(admin: TestClient):
    response = create(admin, ["ОПК-1", "ОПК-5"], semester=5)
    assert response.status_code == 201, response.text
    test = response.json()
    # По 20 вопросов на компетенцию, по 5 на вариант — 4 варианта по 10 вопросов.
    assert (test["variant_count"], test["questions_per_variant"], test["semester"]) == (4, 10, 5)
    detail = admin.get(f"/tests/{test['id']}").json()
    variants = [{q["id"] for q in v["questions"]} for v in detail["variants"]]
    assert [len(v) for v in variants] == [10, 10, 10, 10]
    assert len(set().union(*variants)) == 40  # ни один вопрос не повторяется
    opk1 = by_code(admin, "ОПК-1")["id"]
    for v in detail["variants"]:
        assert sum(q["competency_id"] == opk1 for q in v["questions"]) == 5


def test_variant_count_limited_by_poorest_competency(admin: TestClient):
    # ПК-1 в «Программировании» — 12 вопросов, ОПК-1 в «Математике» — 20: хватает на 2 варианта.
    response = create(admin, ["ПК-1", "ОПК-1"], disciplines=["Программирование", "Математика"])
    assert response.json()["variant_count"] == 2


def test_questions_only_from_selected_disciplines(admin: TestClient):
    test = create(admin, ["ПК-2"], k=4, disciplines=["Технологии программирования"]).json()
    allowed = discipline_id(admin, "Технологии программирования")
    questions = {q["id"]: q for q in admin.get("/questions").json()}
    assert {questions[q]["discipline_id"] for q in test["question_ids"]} == {allowed}
    assert test["discipline_ids"] == [allowed]


def test_shortage_lists_every_competency(admin: TestClient):
    response = create(admin, ["ПК-1", "ПК-2"], k=10, disciplines=["Технологии программирования"])
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "в выбранных дисциплинах" in detail
    assert "ПК-1 — 8 из 10" in detail
    assert "ПК-2" not in detail  # их 12, хватает


def test_unknown_field_is_rejected(admin: TestClient):
    response = create(admin, ["ПК-1"], discipline_id=1)
    assert response.status_code == 422


def test_students_get_different_variants_that_persist(admin: TestClient, login):
    ctx = assign(admin, ["ОПК-5"], per_competency=5)  # 4 варианта
    starts = {}
    for name in ["student1", "student2", "student3"]:
        client = login(name, "student123")
        body = client.post("/me/attempts", json={"assignment_id": ctx["assignment"]["id"]})
        assert body.status_code == 201, body.text
        starts[name] = (client, body.json())
    question_sets = [frozenset(q["id"] for q in b["questions"]) for _, b in starts.values()]
    assert len(set(question_sets)) == 3  # три студента — три разных варианта
    assert all(len(s) == 5 for s in question_sets)

    client, first = starts["student1"]
    again = client.post("/me/attempts", json={"assignment_id": ctx["assignment"]["id"]}).json()
    assert again == first  # тот же вариант, тот же порядок вопросов и ответов

    correct = correct_answers(admin)
    result = client.post(
        f"/me/attempts/{first['attempt_id']}/submit",
        json={
            "answers": [{"question_id": q["id"], **correct[q["id"]]} for q in first["questions"]]
        },
    ).json()
    assert (result["score"], result["max_score"]) == (5, 5)


def test_answer_from_another_variant_is_rejected(admin: TestClient, login):
    ctx = assign(admin, ["ОПК-5"], per_competency=5)
    client = login("student1", "student123")
    body = client.post("/me/attempts", json={"assignment_id": ctx["assignment"]["id"]}).json()
    mine = {q["id"] for q in body["questions"]}
    foreign = next(q for q in ctx["test"]["question_ids"] if q not in mine)
    response = client.post(
        f"/me/attempts/{body['attempt_id']}/submit",
        json={"answers": [{"question_id": foreign, **correct_answers(admin)[foreign]}]},
    )
    assert response.status_code == 404


def test_test_detail_shows_progress(admin: TestClient, student: TestClient):
    ctx = assign(admin, ["ОПК-5"], per_competency=5)
    student.post("/me/attempts", json={"assignment_id": ctx["assignment"]["id"]})
    detail = admin.get(f"/tests/{ctx['test']['id']}").json()
    [a] = detail["assignments"]
    assert (a["group_name"], a["started"], a["finished"]) == ("ПИ-21", 1, 0)


def test_delete_test_and_assignment_only_before_attempts(admin: TestClient, student: TestClient):
    ctx = assign(admin, ["ОПК-5"])
    test_id, assignment_id = ctx["test"]["id"], ctx["assignment"]["id"]
    student.post("/me/attempts", json={"assignment_id": assignment_id})
    assert admin.delete(f"/assignments/{assignment_id}").status_code == 409
    assert admin.delete(f"/tests/{test_id}").status_code == 409

    fresh = create(admin, ["ОПК-1"]).json()
    g = group(admin)
    a = admin.post("/assignments", json={"test_id": fresh["id"], "group_id": g["id"]}).json()
    assert admin.delete(f"/assignments/{a['id']}").status_code == 204
    admin.post("/assignments", json={"test_id": fresh["id"], "group_id": g["id"]})
    assert admin.delete(f"/tests/{fresh['id']}").status_code == 204
    assert admin.get(f"/tests/{fresh['id']}").status_code == 404
    # вопросы удалённого теста снова можно править без ограничений
    assert not any(
        q["in_use"] for q in admin.get("/questions").json() if q["id"] in fresh["question_ids"]
    )


def test_curriculum_crud(admin: TestClient):
    direction = admin.get("/directions").json()[0]
    discipline = admin.post("/disciplines", json={"name": "Философия"}).json()
    entry = {
        "direction_id": direction["id"],
        "discipline_id": discipline["id"],
        "first_semester": 3,
        "last_semester": 4,
    }
    created = admin.post("/curriculum", json=entry)
    assert created.status_code == 201, created.text
    assert admin.post("/curriculum", json=entry).status_code == 409  # дубль
    bad = admin.post("/curriculum", json={**entry, "first_semester": 5})
    assert bad.status_code == 422
    entry_id = created.json()["id"]
    updated = admin.put(f"/curriculum/{entry_id}", json={**entry, "last_semester": 6})
    assert updated.json()["last_semester"] == 6
    listed = admin.get("/curriculum", params={"direction_id": direction["id"]}).json()
    assert entry_id in {e["id"] for e in listed}
    assert admin.delete(f"/curriculum/{entry_id}").status_code == 204
