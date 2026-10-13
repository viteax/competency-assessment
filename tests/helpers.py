from fastapi.testclient import TestClient


def by_code(client: TestClient, code: str) -> dict:
    return next(c for c in client.get("/competencies").json() if c["code"] == code)


def discipline_id(client: TestClient, name: str) -> int:
    return next(d["id"] for d in client.get("/disciplines").json() if d["name"] == name)


def correct_options(client: TestClient) -> dict[int, int]:
    """question_id -> id правильного варианта (из админского эндпоинта банка вопросов)."""
    return {
        q["id"]: next(o["id"] for o in q["options"] if o["is_correct"])
        for q in client.get("/questions").json()
    }
