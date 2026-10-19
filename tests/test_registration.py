"""Самостоятельная регистрация студента по ФИО и вход по ФИО."""

from fastapi.testclient import TestClient

from tests.helpers import student_id


def group_id(client: TestClient, name: str = "ПИ-21") -> int:
    return next(g["id"] for g in client.get("/auth/groups").json() if g["name"] == name)


def add_student(admin: TestClient, full_name: str, group: int) -> int:
    response = admin.post("/students", json={"full_name": full_name, "group_id": group})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def register(client: TestClient, group: int, full_name: str, password="Свой-пароль-2026"):
    return client.post(
        "/auth/register", json={"group_id": group, "full_name": full_name, "password": password}
    )


def test_groups_listed_without_login(client: TestClient):
    assert [g["name"] for g in client.get("/auth/groups").json()] == ["ПИ-21"]


def test_register_and_login_by_full_name(admin: TestClient, client: TestClient):
    g = group_id(client)
    add_student(admin, "Ёлкина Алёна Сергеевна", g)
    response = register(client, g, "  елкина   алена сергеевна ")
    assert response.status_code == 201, response.text
    assert response.json() == {"username": "Ёлкина Алёна Сергеевна"}

    # Входит по ФИО — без учёта регистра, «ё/е» и лишних пробелов; пароль менять не нужно.
    token = client.post(
        "/auth/token",
        data={"username": "ЕЛКИНА  АЛЕНА СЕРГЕЕВНА", "password": "Свой-пароль-2026"},
    )
    assert token.status_code == 200, token.text
    me = client.get("/me", headers={"Authorization": f"Bearer {token.json()['access_token']}"})
    assert (me.json()["role"], me.json()["must_change_password"]) == ("student", False)
    user = next(u for u in admin.get("/users").json() if u["username"] == "Ёлкина Алёна Сергеевна")
    assert user["created_at"]  # администратору видно, когда учётка создана


def test_unknown_student_is_told_clearly(client: TestClient):
    response = register(client, group_id(client), "Неизвестный Студент Студентович")
    assert response.status_code == 404
    assert "нет в списке группы ПИ-21" in response.json()["detail"]


def test_second_registration_refused(admin: TestClient, client: TestClient):
    # У Иванова учётка уже есть (демо-данные).
    response = register(client, group_id(client), "Иванов Иван Иванович")
    assert response.status_code == 409
    assert "уже зарегистрирован" in response.json()["detail"]


def test_weak_password_refused(admin: TestClient, client: TestClient):
    g = group_id(client)
    add_student(admin, "Смирнова Ольга Петровна", g)
    assert register(client, g, "Смирнова Ольга Петровна", "12345678").status_code == 400


def test_full_namesake_in_another_group(admin: TestClient, client: TestClient):
    direction = admin.get("/directions").json()[0]["id"]
    other = admin.post("/groups", json={"name": "ПИ-22", "direction_id": direction}).json()
    add_student(admin, "Кузнецов Андрей Ильич", group_id(client))
    add_student(admin, "Кузнецов Андрей Ильич", other["id"])
    first = register(client, group_id(client), "Кузнецов Андрей Ильич")
    second = register(client, other["id"], "Кузнецов Андрей Ильич")
    assert first.json()["username"] == "Кузнецов Андрей Ильич"
    assert second.json()["username"] == "Кузнецов Андрей Ильич (ПИ-22)"


def test_guessing_names_is_slowed_down(client: TestClient):
    g = group_id(client)
    statuses = [register(client, g, f"Перебор Номер {i}").status_code for i in range(6)]
    assert statuses[:5] == [404] * 5
    assert statuses[5] == 429


def test_admin_still_resets_password(admin: TestClient, client: TestClient):
    g = group_id(client)
    sid = add_student(admin, "Волков Денис Олегович", g)
    register(client, g, "Волков Денис Олегович")
    user = next(u for u in admin.get("/users").json() if u["student_id"] == sid)
    reset = admin.post(f"/users/{user['id']}/reset-password")
    assert reset.status_code == 200
    assert student_id(admin, "Волков Денис Олегович") == sid
