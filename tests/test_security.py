"""Безопасность: перебор паролей, смена и сброс паролей, cookie-сессия, CSRF, учётки."""

from fastapi.testclient import TestClient

from app.config import settings
from tests.helpers import assign, student_id

FETCH = {"X-Requested-With": "fetch"}


def token_login(client: TestClient, username: str, password: str):
    return client.post("/auth/token", data={"username": username, "password": password})


# --- перебор паролей -----------------------------------------------------------


def test_login_is_rate_limited(client: TestClient):
    for _ in range(settings.login_max_failures):
        assert token_login(client, "admin", "wrong").status_code == 401
    blocked = token_login(client, "admin", "admin123")  # даже верный пароль — пауза
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == str(settings.login_window_minutes * 60)


def test_successful_login_resets_failures(client: TestClient):
    for _ in range(settings.login_max_failures - 1):
        token_login(client, "admin", "wrong")
    assert token_login(client, "admin", "admin123").status_code == 200
    for _ in range(settings.login_max_failures - 1):
        assert token_login(client, "admin", "wrong").status_code == 401


def test_failures_of_one_user_do_not_block_another(client: TestClient):
    for _ in range(settings.login_max_failures):
        token_login(client, "admin", "wrong")
    assert token_login(client, "student1", "student123").status_code == 200


# --- смена и сброс пароля --------------------------------------------------------


def change(client: TestClient, current: str, new: str):
    body = {"current_password": current, "new_password": new}
    return client.post("/me/password", json=body, headers=FETCH)


def test_new_account_must_change_password(admin: TestClient, login):
    sid = student_id(admin, "Петрова Анна Сергеевна")
    old = next(u for u in admin.get("/users").json() if u["student_id"] == sid)
    admin.delete(f"/users/{old['id']}")
    admin.post(
        "/users",
        json={"username": "petrova", "password": "temp-pass", "role": "student", "student_id": sid},
    )
    client = login("petrova", "temp-pass")
    assert client.get("/me").json()["must_change_password"] is True
    blocked = client.get("/me/assignments")
    assert blocked.status_code == 403 and "смените" in blocked.json()["detail"]

    assert change(client, "temp-pass", "short").status_code == 400  # короткий
    assert change(client, "temp-pass", "PETROVA").status_code == 400  # совпадает с логином
    assert change(client, "nope", "good-pass-1").status_code == 400  # неверный текущий
    assert change(client, "temp-pass", "good-pass-1").status_code == 204

    # Старый токен отозван — нужно войти заново.
    assert client.get("/me").status_code == 401
    fresh = login("petrova", "good-pass-1")
    assert fresh.get("/me/assignments").status_code == 200


def test_admin_reset_password_revokes_sessions(admin: TestClient, student: TestClient, login):
    user = next(u for u in admin.get("/users").json() if u["username"] == "student1")
    reset = admin.post(f"/users/{user['id']}/reset-password").json()
    assert reset["username"] == "student1" and len(reset["password"]) >= 10
    assert student.get("/me").status_code == 401  # прежняя сессия больше не действует
    client = login("student1", reset["password"])
    assert client.get("/me").json()["must_change_password"] is True


# --- cookie-сессия и CSRF ----------------------------------------------------------


def test_cookie_session_and_csrf(client: TestClient):
    response = token_login(client, "student1", "student123")
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert "secure" not in cookie  # в dev без HTTPS; в prod флаг включается

    assert client.get("/me").json()["username"] == "student1"  # без заголовка Authorization
    body = {"current_password": "student123", "new_password": "another-pass"}
    assert client.post("/me/password", json=body).status_code == 403  # нет X-Requested-With
    assert client.post("/me/password", json=body, headers=FETCH).status_code == 204

    client.post("/auth/logout")
    assert client.get("/me").status_code == 401


def test_bearer_does_not_need_csrf_header(client: TestClient):
    token = token_login(client, "admin", "admin123").json()["access_token"]
    api = TestClient(client.app, headers={"Authorization": f"Bearer {token}"})
    assert api.post("/directions", json={"code": "01.03.02", "name": "ПМИ"}).status_code == 201


def test_tampered_token(client: TestClient):
    token = token_login(client, "admin", "admin123").json()["access_token"]
    api = TestClient(client.app, headers={"Authorization": f"Bearer {token[:-2]}xx"})
    assert api.get("/me").status_code == 401


# --- управление студентами и учётками ----------------------------------------------


def test_edit_and_delete_student(admin: TestClient):
    sid = student_id(admin, "Сидоров Пётр Алексеевич")
    group_id = admin.get("/groups").json()[0]["id"]
    updated = admin.put(
        f"/students/{sid}",
        json={"full_name": "Сидоров Пётр Андреевич", "group_id": group_id, "email": "s@x.ru"},
    ).json()
    assert (updated["full_name"], updated["email"]) == ("Сидоров Пётр Андреевич", "s@x.ru")
    assert admin.delete(f"/students/{sid}").status_code == 204
    assert all(u["student_id"] != sid for u in admin.get("/users").json())  # учётка тоже удалена


def test_student_with_results_cannot_be_deleted(admin: TestClient, student: TestClient):
    ctx = assign(admin, ["ПК-1"])
    attempt = student.post("/me/attempts", json={"assignment_id": ctx["assignment"]["id"]}).json()
    student.post(f"/me/attempts/{attempt['attempt_id']}/submit", json={"answers": []})
    response = admin.delete(f"/students/{student_id(admin)}")
    assert response.status_code == 409 and "результаты" in response.json()["detail"]


def test_admin_cannot_delete_self(admin: TestClient):
    me = admin.get("/me").json()
    assert admin.delete(f"/users/{me['id']}").status_code == 409


# --- заголовки и журнал --------------------------------------------------------


def test_security_headers(client: TestClient):
    page = client.get("/ui/")
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert page.headers["X-Frame-Options"] == "DENY"
    csp = page.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp and "script-src" not in csp  # скрипты только свои
    assert "Content-Security-Policy" not in client.get("/docs").headers  # Swagger с CDN


def test_audit_log(admin: TestClient, student: TestClient):
    admin.post("/directions", json={"code": "01.03.02", "name": "ПМИ"})
    admin.post("/directions", json={"code": "01.03.02", "name": "дубль"})  # 409 тоже пишется
    admin.get("/directions")  # чтение не пишется
    entries = admin.get("/audit").json()
    assert [(e["username"], e["method"], e["path"], e["status_code"]) for e in entries[:2]] == [
        ("admin", "POST", "/directions", 409),
        ("admin", "POST", "/directions", 201),
    ]
    assert all(e["method"] != "GET" for e in entries)
    assert admin.get("/audit", params={"username": "student1"}).json() == []
    assert student.get("/audit").status_code == 403


def test_session_probe(client: TestClient):
    assert client.get("/auth/session").json() is None  # гость — 200 и null, а не 401
    token_login(client, "student1", "student123")
    assert client.get("/auth/session").json()["username"] == "student1"
