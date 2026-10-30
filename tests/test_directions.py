"""У каждого направления свои компетенции и дисциплины: одинаковые коды в разных ОП – разные
компетенции, связи и тесты не смешивают направления."""

import pytest
from fastapi.testclient import TestClient

from app.models import profile_key
from tests.helpers import assign, by_code, demo_direction, discipline_id, student_id


@pytest.fixture
def other(admin: TestClient) -> dict:
    """Второе направление со своей ПК-1, дисциплиной и группой."""
    direction = admin.post(
        "/directions", json={"code": "15.04.06", "name": "Мехатроника и робототехника"}
    ).json()
    pk1 = admin.post(
        "/competencies",
        json={
            "direction_id": direction["id"],
            "code": "ПК-1",
            "kind": "ПК",
            "description": "Способен проектировать мехатронные системы",
        },
    )
    assert pk1.status_code == 201, pk1.text
    discipline = admin.post(
        "/disciplines",
        json={
            "direction_id": direction["id"],
            "name": "Математика",  # то же название, что в демо-направлении
            "kind": "practice",
            "competency_ids": [pk1.json()["id"]],
        },
    )
    assert discipline.status_code == 201, discipline.text
    group = admin.post("/groups", json={"name": "МР-25", "direction_id": direction["id"]})
    return {
        "direction": direction,
        "pk1": pk1.json(),
        "discipline": discipline.json(),
        "group": group.json(),
    }


def test_same_code_in_two_directions(admin: TestClient, other: dict):
    mine = admin.get("/competencies", params={"direction_id": other["direction"]["id"]}).json()
    assert [c["code"] for c in mine] == ["ПК-1"]
    demo = admin.get("/competencies", params={"direction_id": demo_direction(admin)}).json()
    assert "ПК-1" in [c["code"] for c in demo] and other["pk1"]["id"] not in [c["id"] for c in demo]
    disciplines = admin.get("/disciplines", params={"direction_id": other["direction"]["id"]})
    assert [(d["name"], d["kind"]) for d in disciplines.json()] == [("Математика", "practice")]


def test_discipline_takes_only_its_direction_competencies(admin: TestClient, other: dict):
    demo_pk2 = by_code(admin, "ПК-2")
    response = admin.put(
        f"/disciplines/{other['discipline']['id']}",
        json={"name": "Математика", "competency_ids": [demo_pk2["id"]]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "ПК-2 – компетенции другого учебного плана, а нужны компетенции "
        "плана 15.04.06 Мехатроника и робототехника"
    )
    quota = admin.post(
        "/curriculum",
        json={
            "discipline_id": other["discipline"]["id"],
            "first_semester": 1,
            "last_semester": 1,
            "quotas": [{"competency_id": demo_pk2["id"], "questions": 5}],
        },
    )
    assert quota.status_code == 400


def test_labor_function_links_are_kept_per_direction(admin: TestClient, other: dict):
    tf = next(f for f in admin.get("/labor-functions").json() if f["code"] == "A/02.3")
    demo_links = tf["competency_ids"]
    body = {"code": tf["code"], "name": tf["name"], "competency_ids": [other["pk1"]["id"]]}
    updated = admin.put(
        f"/labor-functions/{tf['id']}", json={**body, "direction_id": other["direction"]["id"]}
    ).json()
    assert sorted(updated["competency_ids"]) == sorted([*demo_links, other["pk1"]["id"]])
    # Связи демо-направления меняются, связь второго направления остается.
    cleared = admin.put(
        f"/labor-functions/{tf['id']}",
        json={**body, "competency_ids": [], "direction_id": demo_direction(admin)},
    ).json()
    assert cleared["competency_ids"] == [other["pk1"]["id"]]
    wrong = admin.put(
        f"/labor-functions/{tf['id']}", json={**body, "direction_id": demo_direction(admin)}
    )
    assert wrong.status_code == 400


def test_question_and_test_stay_in_one_direction(admin: TestClient, other: dict):
    mixed = admin.post(
        "/questions",
        json={
            "competency_id": other["pk1"]["id"],
            "discipline_id": discipline_id(admin, "Программирование"),
            "text": "Что такое мехатроника?",
            "kind": "open",
            "options": [{"text": "наука"}],
        },
    )
    assert mixed.status_code == 400
    assert "разным направлениям" in mixed.json()["detail"]

    response = admin.post(
        "/tests",
        json={
            "title": "Смесь",
            "competency_ids": [by_code(admin, "ПК-2")["id"], other["pk1"]["id"]],
            "questions_per_competency": 1,
        },
    )
    assert response.status_code == 400 and "одному направлению" in response.json()["detail"]

    ctx = assign(admin, ["ПК-1"])  # тест демо-направления
    foreign = admin.post(
        "/assignments", json={"test_id": ctx["test"]["id"], "group_id": other["group"]["id"]}
    )
    assert foreign.status_code == 400
    assert "другого направления" in foreign.json()["detail"]


def test_labor_function_report_uses_student_direction(admin: TestClient, other: dict):
    general = admin.get("/general-functions").json()[0]
    admin.post(
        "/labor-functions",
        json={
            "general_function_id": general["id"],
            "code": "A/09.3",
            "name": "Только для мехатроники",
            "competency_ids": [other["pk1"]["id"]],
        },
    )
    report = admin.get(f"/reports/students/{student_id(admin)}/labor-functions").json()
    codes = [f["code"] for g in report for f in g["functions"]]
    assert "A/09.3" not in codes and "A/02.3" in codes


def test_import_compares_with_chosen_direction(admin: TestClient, other: dict):
    text = "ПК-1 Способен разрабатывать программы".encode()
    for direction, status in [
        (demo_direction(admin), "update"),
        (other["direction"]["id"], "update"),
    ]:
        preview = admin.post(
            "/import/preview",
            files={"file": ("list.txt", text, "text/plain")},
            data={"direction_id": str(direction)},
        ).json()
        assert preview["direction_id"] == direction
        assert preview["competencies"][0]["status"] == status
    fresh = admin.post("/directions", json={"code": "09.03.01", "name": "ИВТ"}).json()
    preview = admin.post(
        "/import/preview",
        files={"file": ("list.txt", text, "text/plain")},
        data={"direction_id": str(fresh["id"])},
    ).json()
    assert preview["competencies"][0]["status"] == "new"


def test_direction_is_deleted_with_its_catalogs_unless_used(admin: TestClient, other: dict):
    assert admin.delete(f"/groups/{other['group']['id']}").status_code == 204
    assert admin.delete(f"/directions/{other['direction']['id']}").status_code == 204
    assert all(c["id"] != other["pk1"]["id"] for c in admin.get("/competencies").json())
    # Демо-направление не удалить: у него группы и вопросы.
    blocked = admin.delete(f"/directions/{demo_direction(admin)}")
    assert blocked.status_code == 409


# --- учебные планы: один код, разные программы и годы ------------------------------------


def _plan(admin: TestClient, **fields):
    return admin.post("/directions", json={"code": "11.03.02", "name": "Связь", **fields})


def test_two_plans_of_one_code(admin: TestClient):
    first = _plan(admin, profile="Оптика", plan_year=2023)
    second = _plan(admin, profile="Оптика", plan_year=2026)
    assert first.status_code == second.status_code == 201
    assert first.json()["label"] == "11.03.02 Связь, Оптика, 2023"
    assert second.json()["id"] != first.json()["id"]


def test_label_omits_empty_parts(admin: TestClient):
    assert _plan(admin).json()["label"] == "11.03.02 Связь"
    assert _plan(admin, plan_year=2024).json()["label"] == "11.03.02 Связь, 2024"


def test_same_plan_conflicts_with_empty_fields_too(admin: TestClient):
    assert _plan(admin).status_code == 201
    assert _plan(admin).status_code == 409
    assert _plan(admin, profile="Оптика").status_code == 201
    assert _plan(admin, profile=" ОПТИКА ").status_code == 409


def test_blank_profile_is_no_profile(admin: TestClient):
    assert _plan(admin).status_code == 201
    assert _plan(admin, profile="   ").status_code == 409


def test_profile_key_ignores_spelling():
    assert profile_key(" «Ёлки»  и Палки ") == profile_key('елки и "палки"')
    assert profile_key(None) == ""


def test_intake_years_come_from_groups(admin: TestClient):
    plan = _plan(admin).json()
    for name, year in (("А-1", 2025), ("А-2", 2024), ("А-3", 2025), ("А-4", None)):
        body = {"name": name, "direction_id": plan["id"], "start_year": year}
        assert admin.post("/groups", json=body).status_code == 201
    found = next(d for d in admin.get("/directions").json() if d["id"] == plan["id"])
    assert found["intake_years"] == [2024, 2025]


# --- перевод группы на другой план ---------------------------------------------------------


def test_move_group_without_assignments(admin: TestClient):
    plan = _plan(admin).json()
    group = next(g for g in admin.get("/groups").json() if g["name"] == "ПИ-21")
    moved = admin.put(f"/groups/{group['id']}", json={**group, "direction_id": plan["id"]})
    assert moved.status_code == 200, moved.text
    assert moved.json()["direction_id"] == plan["id"]


def test_move_group_with_assignment_is_refused(admin: TestClient):
    group = assign(admin, ["ПК-1"])["group"]
    plan = _plan(admin).json()
    moved = admin.put(f"/groups/{group['id']}", json={**group, "direction_id": plan["id"]})
    assert moved.status_code == 409
    assert "назначены тесты" in moved.json()["detail"]
    found = next(g for g in admin.get("/groups").json() if g["id"] == group["id"])
    assert found["direction_id"] == group["direction_id"]


def test_rename_group_with_assignment_still_works(admin: TestClient):
    group = assign(admin, ["ПК-1"])["group"]
    renamed = admin.put(f"/groups/{group['id']}", json={**group, "start_year": 2021})
    assert renamed.status_code == 200, renamed.text
