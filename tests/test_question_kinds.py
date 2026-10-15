"""Задания на соответствие, последовательность и открытого типа: создание, проверка, правка."""

import pytest
from fastapi.testclient import TestClient

from tests.helpers import answer_for, by_code


def create(admin: TestClient, kind: str, options: list[dict], **extra) -> dict:
    response = admin.post(
        "/questions",
        json={
            "competency_id": by_code(admin, "ОПК-5")["id"],
            "text": f"Задание {kind}",
            "kind": kind,
            "options": options,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


MATCHING = [
    {"text": "SSH", "match_index": 4},
    {"text": "HTTP", "match_index": 5},
    {"text": "HTTPS", "match_index": 3},
    {"text": "443"},
    {"text": "22"},
    {"text": "80"},
    {"text": "21"},  # лишний элемент правого столбца
]


def test_create_each_kind(admin: TestClient):
    seq = create(
        admin,
        "sequence",
        [{"text": t} for t in ["первый", "второй", "третий"]],
        difficulty="advanced",
    )
    assert (seq["kind"], seq["difficulty"]) == ("sequence", "advanced")
    assert [o["position"] for o in seq["options"]] == [0, 1, 2]

    opened = create(admin, "open", [{"text": "root"}, {"text": "суперпользователь"}])
    assert all(o["is_correct"] for o in opened["options"])

    matching = create(admin, "matching", MATCHING)
    by_text = {o["text"]: o for o in matching["options"]}
    assert by_text["SSH"]["match_id"] == by_text["22"]["id"]
    assert by_text["HTTPS"]["match_id"] == by_text["443"]["id"]
    assert by_text["21"]["match_id"] is None


@pytest.mark.parametrize(
    ("kind", "options", "message"),
    [
        ("single", [{"text": "a", "is_correct": True}], "не меньше двух"),
        ("single", [{"text": "a"}, {"text": "b"}], "ровно один"),
        ("sequence", [{"text": "a"}], "не меньше двух"),
        ("matching", [{"text": "a", "match_index": 1}, {"text": "1"}], "не меньше двух пар"),
        (
            "matching",
            [{"text": "a", "match_index": 2}, {"text": "b", "match_index": 2}, {"text": "1"}],
            "свой элемент",
        ),
        ("open", [{"text": "x", "match_index": 0}], "только в задании на соответствие"),
        ("open", [{"text": "   "}], "at least 1"),
    ],
)
def test_validation(admin: TestClient, kind, options, message):
    response = admin.post(
        "/questions",
        json={
            "competency_id": by_code(admin, "ОПК-5")["id"],
            "text": "t",
            "kind": kind,
            "options": options,
        },
    )
    assert response.status_code == 422
    assert message in response.text


@pytest.fixture
def lone(admin: TestClient):
    """Создаёт вопрос в отдельной дисциплине и тест только из него."""

    def make(kind: str, options: list[dict]) -> tuple[dict, int]:
        discipline = admin.post("/disciplines", json={"name": f"Дисциплина {kind}"}).json()
        question = create(admin, kind, options, discipline_id=discipline["id"])
        test = admin.post(
            "/tests",
            json={
                "title": f"Тест {kind}",
                "competency_ids": [question["competency_id"]],
                "discipline_ids": [discipline["id"]],
                "questions_per_competency": 1,
            },
        )
        assert test.status_code == 201, test.text
        group = next(g for g in admin.get("/groups").json() if g["name"] == "ПИ-21")
        assignment = admin.post(
            "/assignments", json={"test_id": test.json()["id"], "group_id": group["id"]}
        ).json()
        return question, assignment["id"]

    return make


def submit(student: TestClient, assignment_id: int, answer: dict) -> tuple[dict, dict]:
    started = student.post("/me/attempts", json={"assignment_id": assignment_id}).json()
    [q] = started["questions"]
    result = student.post(
        f"/me/attempts/{started['attempt_id']}/submit",
        json={"answers": [{"question_id": q["id"], **answer}]},
    )
    assert result.status_code == 200, result.text
    return q, result.json()


def test_open_answer_ignores_case_yo_and_punctuation(admin, student, lone):
    question, assignment = lone("open", [{"text": "чёрного"}])
    q, result = submit(student, assignment, {"text": "  «Черного». "})
    assert q["options"] == [] and q["right"] == []  # допустимые ответы студенту не видны
    assert result["score"] == 1


def test_open_wrong_answer(admin, login, lone):
    question, assignment = lone("open", [{"text": "root"}])
    _, result = submit(login("student2", "student123"), assignment, {"text": "admin"})
    assert result["score"] == 0


def test_sequence(admin, login, lone):
    question, assignment = lone("sequence", [{"text": t} for t in "абвгд"])
    q, result = submit(login("student1", "student123"), assignment, answer_for(question))
    assert result["score"] == 1
    assert sorted(o["id"] for o in q["options"]) == sorted(o["id"] for o in question["options"])
    _, wrong = submit(
        login("student2", "student123"), assignment, answer_for(question, correct=False)
    )
    assert wrong["score"] == 0


def test_matching(admin, login, lone):
    question, assignment = lone("matching", MATCHING)
    q, result = submit(login("student1", "student123"), assignment, answer_for(question))
    assert result["score"] == 1
    assert {o["text"] for o in q["options"]} == {"SSH", "HTTP", "HTTPS"}
    assert {o["text"] for o in q["right"]} == {"443", "22", "80", "21"}
    assert "match_id" not in q["options"][0]
    _, wrong = submit(
        login("student2", "student123"), assignment, answer_for(question, correct=False)
    )
    assert wrong["score"] == 0


def test_foreign_elements_rejected(admin, student, lone):
    question, assignment = lone("sequence", [{"text": t} for t in "абв"])
    started = student.post("/me/attempts", json={"assignment_id": assignment}).json()
    response = student.post(
        f"/me/attempts/{started['attempt_id']}/submit",
        json={"answers": [{"question_id": question["id"], "order": [999999]}]},
    )
    assert response.status_code == 400


def test_used_matching_keeps_pairs(admin, lone):
    question, _ = lone("matching", MATCHING)
    question = next(q for q in admin.get("/questions").json() if q["id"] == question["id"])
    ids = [o["id"] for o in question["options"]]
    index = {oid: i for i, oid in enumerate(ids)}
    options = [
        {
            "id": o["id"],
            "text": o["text"] + "!",
            "match_index": index[o["match_id"]] if o["match_id"] else None,
        }
        for o in question["options"]
    ]
    payload = {
        "competency_id": question["competency_id"],
        "text": "уточнено",
        "kind": "matching",
        "discipline_id": question["discipline_id"],
        "options": options,
        "difficulty": "advanced",
    }
    ok = admin.put(f"/questions/{question['id']}", json=payload)
    assert ok.status_code == 200, ok.text
    assert ok.json()["difficulty"] == "advanced"

    swapped = [dict(o) for o in options]
    lefts = [i for i, o in enumerate(swapped) if o["match_index"] is not None]
    a, b = lefts[:2]
    swapped[a]["match_index"], swapped[b]["match_index"] = (
        swapped[b]["match_index"],
        swapped[a]["match_index"],
    )
    response = admin.put(f"/questions/{question['id']}", json={**payload, "options": swapped})
    assert response.status_code == 409


def test_unused_question_can_change_kind(admin: TestClient):
    question = create(admin, "single", [{"text": "a", "is_correct": True}, {"text": "b"}])
    response = admin.put(
        f"/questions/{question['id']}",
        json={
            "competency_id": question["competency_id"],
            "text": "Теперь открытый",
            "kind": "open",
            "options": [{"text": "ответ"}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["kind"] == "open"
    assert [o["text"] for o in response.json()["options"]] == ["ответ"]


def test_used_sequence_keeps_order(admin, lone):
    question, _ = lone("sequence", [{"text": t} for t in "абв"])
    options = [{"id": o["id"], "text": o["text"]} for o in question["options"]]
    payload = {
        "competency_id": question["competency_id"],
        "text": "т",
        "kind": "sequence",
        "discipline_id": question["discipline_id"],
    }
    assert (
        admin.put(f"/questions/{question['id']}", json={**payload, "options": options}).status_code
        == 200
    )
    reordered = admin.put(
        f"/questions/{question['id']}", json={**payload, "options": options[::-1]}
    )
    assert reordered.status_code == 409
