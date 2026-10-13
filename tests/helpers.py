from fastapi.testclient import TestClient


def by_code(admin: TestClient, code: str) -> dict:
    return next(c for c in admin.get("/competencies").json() if c["code"] == code)


def discipline_id(admin: TestClient, name: str) -> int:
    return next(d["id"] for d in admin.get("/disciplines").json() if d["name"] == name)


def correct_options(admin: TestClient) -> dict[int, int]:
    """question_id -> id правильного варианта (из админского эндпоинта банка вопросов)."""
    return {
        q["id"]: next(o["id"] for o in q["options"] if o["is_correct"])
        for q in admin.get("/questions").json()
    }


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
