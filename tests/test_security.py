"""Безопасность: перебор паролей, смена и сброс паролей, cookie-сессия, CSRF, учётки."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.errors import DomainError
from app.services.auth import validate_new_password
from tests.helpers import assign, student_id

FETCH = {"X-Requested-With": "fetch"}


def token_login(client: TestClient, username: str, password: str):
    return client.post("/auth/token", data={"username": username, "password": password})


# --- подбор паролей ----------------------------------------------------------------


def fail_logins(client: TestClient, username: str, times: int) -> None:
    for _ in range(times):
        assert token_login(client, username, "wrong-password").status_code == 401


def test_slowdown_ignores_spelling_of_full_name_login(admin: TestClient, client: TestClient):
    group = client.get("/auth/groups").json()[0]["id"]
    admin.post("/students", json={"full_name": "Ёлкина Алёна Сергеевна", "group_id": group})
    registered = client.post(
        "/auth/register",
        json={
            "group_id": group,
            "full_name": "Ёлкина Алёна Сергеевна",
            "password": "Свой-пароль-2026",
        },
    )
    assert registered.status_code == 201, registered.text

    spellings = [
        "Ёлкина Алёна Сергеевна",
        "ёлкина алёна сергеевна",
        "Елкина  Алена Сергеевна",
        "ЕЛКИНА АЛЕНА  СЕРГЕЕВНА",
        " елкина алена сергеевна ",
    ]
    assert len(spellings) == settings.login_slowdown_after
    for spelling in spellings:
        assert token_login(client, spelling, "wrong-password").status_code == 401
    blocked = token_login(client, "Ёлкина Алёна Сергеевна", "Свой-пароль-2026")
    assert blocked.status_code == 429


def test_login_slows_down_after_failures(client: TestClient):
    fail_logins(client, "student2", settings.login_slowdown_after)
    blocked = token_login(client, "student2", "student123")  # даже верный пароль – подождать
    assert blocked.status_code == 429
    assert 0 < int(blocked.headers["Retry-After"]) <= settings.login_slowdown_seconds


def test_slowdown_is_a_pause_not_a_lockout(client: TestClient, session):
    from app import models

    fail_logins(client, "student2", settings.login_slowdown_after)
    # Прошло больше паузы – владелец снова может войти, неудачи сбрасываются.
    for failure in session.query(models.LoginFailure).all():
        failure.created_at = failure.created_at - timedelta(seconds=settings.login_slowdown_seconds)
    session.commit()
    assert token_login(client, "student2", "student123").status_code == 200
    assert session.query(models.LoginFailure).count() == 0


def test_attack_on_one_login_does_not_affect_others(client: TestClient):
    # На кампусе все с одного IP: подбор пароля к чужому логину не мешает остальным.
    fail_logins(client, "student2", settings.login_slowdown_after)
    assert token_login(client, "student2", "x").status_code == 429
    assert token_login(client, "student1", "student123").status_code == 200


def test_trusted_device_is_not_slowed_down(client: TestClient):
    owner = TestClient(client.app)
    assert token_login(owner, "student2", "student123").status_code == 200  # ставит cookie device
    attacker = TestClient(client.app)
    fail_logins(attacker, "student2", settings.login_slowdown_after)
    assert token_login(attacker, "student2", "student123").status_code == 429
    # Владелец со своего браузера входит без ожидания.
    assert token_login(owner, "student2", "student123").status_code == 200


def test_per_ip_ceiling(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "login_max_failures_per_ip", 3)
    for name in ("a1", "a2", "a3"):
        fail_logins(client, name, 1)
    assert token_login(client, "student1", "student123").status_code == 429


def test_unknown_login_is_indistinguishable(client: TestClient):
    unknown = token_login(client, "no-such-user", "whatever-pass")
    wrong = token_login(client, "student1", "whatever-pass")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


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

    # Старый токен отозван – нужно войти заново.
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
    session_cookie = [
        c for c in response.headers.get_list("set-cookie") if c.startswith("session=")
    ]
    assert "max-age" not in session_cookie[0].lower()  # исчезает при закрытии браузера

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
    assert "unsafe-inline" not in csp  # ни inline-скриптов, ни inline-стилей
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
    assert client.get("/auth/session").json() is None  # гость – 200 и null, а не 401
    token_login(client, "student1", "student123")
    assert client.get("/auth/session").json()["username"] == "student1"


def test_idle_session_expires(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "session_idle_minutes", 0)  # токен истекает сразу
    token_login(client, "student1", "student123")
    assert client.get("/me").status_code == 401


def test_session_sliding_window(client: TestClient):
    from app.api import deps

    token_login(client, "student1", "student123")
    original = deps.timedelta
    try:
        # Делаем «половину срока» больше всего срока – любой запрос попадает в окно продления.
        deps.timedelta = lambda minutes: original(minutes=minutes * 4)
        response = client.get("/me")
    finally:
        deps.timedelta = original
    assert response.status_code == 200
    assert response.headers["set-cookie"].startswith("session=")


@pytest.mark.parametrize(
    "password", ["12345678", "qwerty123", "ЙЦУКЕНГШ", "aaaaaaaa", "0101200512", "my-student1-pw"]
)
def test_weak_passwords_rejected(password: str):
    with pytest.raises(DomainError):
        validate_new_password(password, "student1")


def test_reasonable_password_accepted():
    validate_new_password("кот-в-сапогах-7", "student1")
