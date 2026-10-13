"""Отчёты: число запросов к БД и настраиваемый порог «компетенция сформирована»."""

from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import event

from tests.helpers import assign, correct_options


@contextmanager
def count_queries(session):
    engine = session.get_bind()
    statements: list[str] = []

    def before(_conn, _cursor, statement, *_):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", before)


def add_students(admin: TestClient, group_id: int, count: int) -> None:
    for i in range(count):
        admin.post("/students", json={"full_name": f"Студент {i:02}", "group_id": group_id})


def test_group_report_query_count_does_not_grow_with_students(admin: TestClient, session):
    ctx = assign(admin, ["ПК-1"])
    group_id = ctx["group"]["id"]
    url = f"/reports/groups/{group_id}/competencies"

    with count_queries(session) as small:
        admin.get(url)
    add_students(admin, group_id, 20)
    with count_queries(session) as large:
        report = admin.get(url).json()
    assert len(report["students"]) == 23
    assert len(large) == len(small)  # раньше было +1 запрос на каждого студента


def test_mastery_threshold_setting(admin: TestClient, student: TestClient):
    ctx = assign(admin, ["ПК-1"])
    started = student.post("/me/attempts", json={"assignment_id": ctx["assignment"]["id"]}).json()
    correct = correct_options(admin)
    # 2 верных из 3 — 67 %.
    answers = [
        {"question_id": q["id"], "option_id": correct[q["id"]]} for q in started["questions"][:2]
    ]
    student.post(f"/me/attempts/{started['attempt_id']}/submit", json={"answers": answers})

    def mastered() -> bool:
        return student.get("/me/reports/competencies").json()["competencies"][0]["mastered"]

    assert admin.get("/settings").json() == {"mastery_threshold": 0.6}
    assert mastered() is True
    assert admin.put("/settings", json={"mastery_threshold": 0.75}).status_code == 200
    assert mastered() is False  # отчёты пересчитываются сразу
    assert admin.put("/settings", json={"mastery_threshold": 0}).status_code == 422
    assert admin.put("/settings", json={"mastery_threshold": 1.5}).status_code == 422
    assert student.get("/settings").status_code == 403
