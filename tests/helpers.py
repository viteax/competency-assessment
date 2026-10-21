from fastapi.testclient import TestClient


def by_code(admin: TestClient, code: str) -> dict:
    return next(c for c in admin.get("/competencies").json() if c["code"] == code)


def discipline_id(admin: TestClient, name: str) -> int:
    return next(d["id"] for d in admin.get("/disciplines").json() if d["name"] == name)


def answer_for(question: dict, correct: bool = True) -> dict:
    """Поля ответа на вопрос из банка (QuestionOut): верного или заведомо неверного."""
    options = question["options"]
    match question["kind"]:
        case "open":
            return {"text": options[0]["text"].upper() if correct else "заведомо не то"}
        case "sequence":
            order = [o["id"] for o in options]
            return {"order": order if correct else order[::-1]}
        case "matching":
            pairs = {o["id"]: o["match_id"] for o in options if o["match_id"]}
            if not correct:
                left = list(pairs)
                pairs = {left[0]: pairs[left[1]], left[1]: pairs[left[0]]}
            return {"pairs": pairs}


def correct_answers(admin: TestClient) -> dict[int, dict]:
    """question_id -> поля верного ответа (по админскому эндпоинту банка вопросов)."""
    return {q["id"]: answer_for(q) for q in admin.get("/questions").json()}


def assign(admin: TestClient, codes: list[str], per_competency: int = 3) -> dict:
    """Собирает тест по компетенциям и назначает его группе ПИ-21."""
    test = admin.post(
        "/tests",
        json={
            "title": "Входной контроль",
            "competency_ids": [by_code(admin, c)["id"] for c in codes],
            "questions_per_competency": per_competency,
        },
    )
    assert test.status_code == 201, test.text
    group = next(g for g in admin.get("/groups").json() if g["name"] == "ПИ-21")
    assignment = admin.post(
        "/assignments", json={"test_id": test.json()["id"], "group_id": group["id"]}
    )
    assert assignment.status_code == 201, assignment.text
    return {"test": test.json(), "assignment": assignment.json(), "group": group}


def student_id(admin: TestClient, full_name: str = "Иванов Иван Иванович") -> int:
    return next(s["id"] for s in admin.get("/students").json() if s["full_name"] == full_name)
