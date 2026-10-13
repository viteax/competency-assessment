import pytest
from fastapi.testclient import TestClient

from app.security import hash_password, verify_password
from tests.helpers import student_id


def test_password_hashing():
    h = hash_password("secret")
    assert h != hash_password("secret")  # соль
    assert verify_password("secret", h)
    assert not verify_password("wrong", h)
    assert not verify_password("secret", "garbage")


def test_wrong_password(client: TestClient):
    response = client.post("/auth/token", data={"username": "admin", "password": "nope"})
    assert response.status_code == 401


def test_bad_token(client: TestClient):
    client.headers["Authorization"] = "Bearer not-a-jwt"
    assert client.get("/me").status_code == 401


def test_me(admin: TestClient, student: TestClient):
    assert admin.get("/me").json()["role"] == "admin"
    me = student.get("/me").json()
    assert (me["role"], me["student_id"]) == ("student", student_id(admin))


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/competencies"),
        ("get", "/questions"),  # банк вопросов содержит правильные ответы
        ("get", "/students"),
        ("post", "/tests"),
        ("post", "/assignments"),
        ("get", "/reports/groups/1/competencies"),
        ("get", "/users"),
    ],
)
def test_admin_endpoints(client: TestClient, student: TestClient, method: str, path: str):
    assert getattr(client, method)(path).status_code == 401
    assert getattr(student, method)(path).status_code == 403


@pytest.mark.parametrize("path", ["/me/assignments", "/me/reports/competencies"])
def test_student_endpoints(client: TestClient, admin: TestClient, path: str):
    assert client.get(path).status_code == 401
    assert admin.get(path).status_code == 403


def test_create_user_validation(admin: TestClient):
    no_student = admin.post(
        "/users", json={"username": "kid", "password": "secret1", "role": "student"}
    )
    assert no_student.status_code == 422
    admin_with_student = admin.post(
        "/users",
        json={"username": "boss", "password": "secret1", "role": "admin", "student_id": 1},
    )
    assert admin_with_student.status_code == 422
    duplicate = admin.post(
        "/users", json={"username": "admin", "password": "secret1", "role": "admin"}
    )
    assert duplicate.status_code == 409


def test_web_ui_is_served(client: TestClient):
    root = client.get("/", follow_redirects=False)
    assert (root.status_code, root.headers["location"]) == (307, "/ui/")
    page = client.get("/ui/")
    assert page.status_code == 200 and "app.js" in page.text
    assert client.get("/ui/app.js").status_code == 200
