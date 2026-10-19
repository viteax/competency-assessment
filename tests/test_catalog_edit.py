"""Редактирование справочников и банка вопросов администратором."""

from fastapi.testclient import TestClient

from tests.helpers import assign, by_code, discipline_id


def test_direction_and_group(admin: TestClient):
    direction = admin.post("/directions", json={"code": "01.03.02", "name": "ПМИ"}).json()
    renamed = admin.put(
        f"/directions/{direction['id']}",
        json={"code": "01.03.02", "name": "Прикладная математика и информатика"},
    )
    assert renamed.json()["name"] == "Прикладная математика и информатика"

    group = admin.post("/groups", json={"name": "ПМИ-21", "direction_id": direction["id"]}).json()
    assert (
        admin.put(
            f"/groups/{group['id']}", json={"name": "ПМИ-22", "direction_id": direction["id"]}
        ).json()["name"]
        == "ПМИ-22"
    )

    # Нельзя удалить направление, пока в нём есть группа.
    blocked = admin.delete(f"/directions/{direction['id']}")
    assert blocked.status_code == 409 and "группы" in blocked.json()["detail"]
    assert admin.delete(f"/groups/{group['id']}").status_code == 204
    assert admin.delete(f"/directions/{direction['id']}").status_code == 204


def test_group_with_students_is_protected(admin: TestClient):
    group = next(g for g in admin.get("/groups").json() if g["name"] == "ПИ-21")
    assert admin.delete(f"/groups/{group['id']}").status_code == 409


def test_competency_and_indicators(admin: TestClient):
    competency = admin.post(
        "/competencies", json={"code": "ПК-9", "kind": "ПК", "description": "черновик"}
    ).json()
    updated = admin.put(
        f"/competencies/{competency['id']}",
        json={"code": "ПК-3", "kind": "ПК", "description": "Способен проектировать ПО"},
    ).json()
    assert (updated["code"], updated["description"]) == ("ПК-3", "Способен проектировать ПО")

    indicator = admin.post(
        "/indicators",
        json={"competency_id": competency["id"], "code": "ПК-3.1", "description": "Знает"},
    ).json()
    assert (
        admin.put(
            f"/indicators/{indicator['id']}", json={"code": "ПК-3.1", "description": "Знает UML"}
        ).json()["description"]
        == "Знает UML"
    )
    assert [
        i["code"] for i in admin.get(f"/indicators?competency_id={competency['id']}").json()
    ] == ["ПК-3.1"]
    assert admin.delete(f"/indicators/{indicator['id']}").status_code == 204
    assert admin.delete(f"/competencies/{competency['id']}").status_code == 204


def test_competency_with_questions_is_protected(admin: TestClient):
    pk1 = by_code(admin, "ПК-1")
    assert admin.delete(f"/competencies/{pk1['id']}").status_code == 409
    assert admin.delete(f"/indicators/{pk1['indicators'][0]['id']}").status_code == 409
    assert by_code(admin, "ПК-1")["indicators"] == pk1["indicators"]


def test_duplicate_code_on_update(admin: TestClient):
    pk2 = by_code(admin, "ПК-2")
    response = admin.put(
        f"/competencies/{pk2['id']}", json={"code": "ПК-1", "kind": "ПК", "description": "x"}
    )
    assert response.status_code == 409


def test_discipline(admin: TestClient):
    pk1, pk2 = by_code(admin, "ПК-1"), by_code(admin, "ПК-2")
    discipline = admin.post(
        "/disciplines", json={"name": "Тестирование ПО", "competency_ids": [pk1["id"]]}
    ).json()
    updated = admin.put(
        f"/disciplines/{discipline['id']}",
        json={"name": "Тестирование и отладка", "competency_ids": [pk2["id"]]},
    ).json()
    assert (updated["name"], updated["competency_ids"]) == ("Тестирование и отладка", [pk2["id"]])
    assert admin.delete(f"/disciplines/{discipline['id']}").status_code == 204
    # Дисциплину с вопросами удалить нельзя.
    math = discipline_id(admin, "Математика")
    assert admin.delete(f"/disciplines/{math}").status_code == 409


def test_standard_otf_tf(admin: TestClient):
    pk1 = by_code(admin, "ПК-1")
    standard = admin.post("/standards", json={"code": "06.015", "name": "Тестировщик"}).json()
    assert (
        admin.put(
            f"/standards/{standard['id']}",
            json={"code": "06.004", "name": "Специалист по тестированию в области ИТ"},
        ).json()["code"]
        == "06.004"
    )

    general = admin.post(
        "/general-functions",
        json={
            "standard_id": standard["id"],
            "code": "A",
            "name": "Тестирование",
            "qualification_level": 4,
        },
    ).json()
    tf = admin.post(
        "/labor-functions",
        json={
            "general_function_id": general["id"],
            "code": "A/01.4",
            "name": "Тест-кейсы",
            "competency_ids": [pk1["id"]],
        },
    ).json()
    assert tf["competency_ids"] == [pk1["id"]]
    tf = admin.put(
        f"/labor-functions/{tf['id']}",
        json={"code": "A/01.4", "name": "Разработка тест-кейсов", "competency_ids": []},
    ).json()
    assert (tf["name"], tf["competency_ids"]) == ("Разработка тест-кейсов", [])
    assert (
        admin.put(
            f"/general-functions/{general['id']}",
            json={"code": "A", "name": "Тестирование ПО", "qualification_level": 5},
        ).json()["qualification_level"]
        == 5
    )

    # Удаление стандарта удаляет его ОТФ и ТФ.
    assert admin.delete(f"/standards/{standard['id']}").status_code == 204
    assert all(g["standard_id"] != standard["id"] for g in admin.get("/general-functions").json())
    assert all(f["id"] != tf["id"] for f in admin.get("/labor-functions").json())


def _new_question(admin: TestClient) -> dict:
    pk1 = by_code(admin, "ПК-1")
    response = admin.post(
        "/questions",
        json={
            "competency_id": pk1["id"],
            "indicator_id": pk1["indicators"][0]["id"],
            "text": "Черновик",
            "kind": "open",
            "options": [{"text": "a"}, {"text": "b"}],
        },
    )
    assert response.status_code == 201
    assert response.json()["in_use"] is False
    return response.json()


def test_unused_question_can_be_fully_edited_and_deleted(admin: TestClient):
    q = _new_question(admin)
    pk2 = by_code(admin, "ПК-2")
    updated = admin.put(
        f"/questions/{q['id']}",
        json={
            "competency_id": pk2["id"],
            "text": "Расположите шаги рефакторинга по порядку",
            "kind": "sequence",
            "options": [{"text": "x"}, {"text": "y"}, {"text": "z"}],
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert (body["competency_id"], body["indicator_id"], len(body["options"])) == (
        pk2["id"],
        None,
        3,
    )
    assert body["kind"] == "sequence"
    assert [o["text"] for o in body["options"]] == ["x", "y", "z"]
    assert admin.delete(f"/questions/{q['id']}").status_code == 204


def test_question_used_in_test_allows_only_wording(admin: TestClient):
    ctx = assign(admin, ["ПК-1"])
    questions = {q["id"]: q for q in admin.get("/questions").json()}
    # Задание открытого типа (в тесте бывают и задания других типов – порядок случайный).
    q = next(questions[i] for i in ctx["test"]["question_ids"] if questions[i]["kind"] == "open")
    assert q["in_use"] is True

    payload = {
        "competency_id": q["competency_id"],
        "indicator_id": q["indicator_id"],
        "discipline_id": q["discipline_id"],
        "text": q["text"] + " (уточнено)",
        "kind": q["kind"],
        "options": [{**o, "text": o["text"] + "!"} for o in q["options"]],
    }
    ok = admin.put(f"/questions/{q['id']}", json=payload)
    assert ok.status_code == 200, ok.text
    assert ok.json()["text"].endswith("(уточнено)")
    assert [o["id"] for o in ok.json()["options"]] == [o["id"] for o in q["options"]]

    # Сменить тип нельзя.
    as_sequence = {**payload, "kind": "sequence", "options": [{"text": "а"}, {"text": "б"}]}
    response = admin.put(f"/questions/{q['id']}", json=as_sequence)
    assert response.status_code == 409

    # Добавить принимаемый ответ нельзя.
    more = [*payload["options"], {"text": "новый"}]
    assert admin.put(f"/questions/{q['id']}", json={**payload, "options": more}).status_code == 409

    # Удалить нельзя.
    assert admin.delete(f"/questions/{q['id']}").status_code == 409


def test_edit_endpoints_require_admin(student: TestClient):
    assert student.put("/directions/1", json={"code": "x", "name": "y"}).status_code == 403
    assert student.delete("/questions/1").status_code == 403
