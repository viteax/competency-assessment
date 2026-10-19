import io
import json

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.services.student_columns import guess_mapping

# Выгрузка участников курса Moodle («Скачать данные таблицы как CSV»).
MOODLE_PARTICIPANTS = (
    "Имя / Фамилия,Адрес электронной почты,Роли,Группы,Последний доступ к курсу\n"
    "Иван Иванович Иванов,ivanov@stud.example.ru,Студент,ПИ-21,1 день\n"
    "Мария Олеговна Новикова,novikova@stud.example.ru,Студент,ПИ-22,2 дня\n"
    'Пётр Сергеевич Козлов,kozlov@stud.example.ru,Студент,"ПИ-22, Подгруппа 1",никогда\n'
    "Анна Викторовна Преподавателева,teacher@example.ru,Преподаватель,,сегодня\n"
)


def gradebook_xlsx() -> bytes:
    """Экспорт журнала оценок Moodle: имя и фамилия отдельно, группа в «Отдел»."""
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "Имя",
            "Фамилия",
            "Индивидуальный номер",
            "Учреждение",
            "Отдел",
            "Адрес электронной почты",
            "Тест 1 (Значение)",
        ]
    )
    ws.append(["Ольга", "Смирнова", "123456", "ТУСУР", "ПИ-23", "smirnova@stud.example.ru", 8])
    ws.append(["Олег", "Фёдоров", "123457", "ТУСУР", "ПИ-23", "fedorov@stud.example.ru", None])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def upload(admin: TestClient, name: str, data: bytes, mapping: dict | None = None) -> dict:
    form = {"mapping": json.dumps(mapping)} if mapping else None
    response = admin.post("/import/students/preview", files={"file": (name, data)}, data=form)
    assert response.status_code == 200, response.text
    return response.json()


def selected(preview: dict) -> list[dict]:
    """Строки, которые админ оставил бы отмеченными: студенты без проблем."""
    keys = ("full_name", "email", "external_id", "login", "group")
    return [
        {k: r[k] for k in keys} for r in preview["rows"] if r["is_student"] and not r["problems"]
    ]


def direction_id(admin: TestClient) -> int:
    return admin.get("/directions").json()[0]["id"]


def test_guess_mapping():
    assert guess_mapping(["Имя / Фамилия", "Адрес электронной почты", "Роли", "Группы"]) == {
        "full_name": 0,
        "last_name": None,
        "first_name": None,
        "middle_name": None,
        "email": 1,
        "external_id": None,
        "login": None,
        "group": 3,
        "program": None,
        "role": 2,
    }
    m = guess_mapping(["Фамилия", "Имя", "Отчество", "Имя пользователя", "Номер зачётной книжки"])
    assert (m["last_name"], m["first_name"], m["middle_name"], m["login"], m["external_id"]) == (
        0,
        1,
        2,
        3,
        4,
    )


def test_moodle_participants_preview(admin: TestClient):
    p = upload(admin, "participants.csv", MOODLE_PARTICIPANTS.encode())
    rows = {r["full_name"]: r for r in p["rows"]}
    assert len(rows) == 4
    # Учитель отмечен как не студент.
    assert rows["Анна Викторовна Преподавателева"]["is_student"] is False
    # Из «ПИ-22, Подгруппа 1» берётся первая группа.
    assert rows["Пётр Сергеевич Козлов"]["group"] == "ПИ-22"
    # Иванов уже есть в ПИ-21 как «Иванов Иван Иванович» – порядок слов не важен.
    ivanov = rows["Иван Иванович Иванов"]
    assert (ivanov["status"], ivanov["external_id"]) == ("update", None)  # добавится e-mail
    assert {r["status"] for n, r in rows.items() if n != "Иван Иванович Иванов"} == {"new"}
    assert p["missing_groups"] == ["ПИ-22"]


def test_apply_creates_groups_students_and_accounts(admin: TestClient, login):
    p = upload(admin, "participants.csv", MOODLE_PARTICIPANTS.encode())
    payload = {"students": selected(p), "direction_id": direction_id(admin)}
    result = admin.post("/import/students/apply", json=payload).json()
    assert (result["created"], result["updated"], result["created_groups"]) == (2, 1, ["ПИ-22"])
    # У Иванова уже есть учётка student1, новые – только у новых студентов.
    accounts = {a["username"]: a for a in result["accounts"]}
    assert set(accounts) == {"novikova", "kozlov"}
    ivanov = next(
        s for s in admin.get("/students").json() if s["email"] == "ivanov@stud.example.ru"
    )
    assert ivanov["full_name"] == "Иванов Иван Иванович"  # ФИО не переписано

    # Выданный логин работает, студент видит себя.
    student = login("novikova", accounts["novikova"]["password"])
    me = student.get("/me").json()
    assert me["role"] == "student"

    # Повторная загрузка того же файла ничего не создаёт.
    again = upload(admin, "participants.csv", MOODLE_PARTICIPANTS.encode())
    assert {r["status"] for r in again["rows"] if r["is_student"]} == {"same"}
    repeat = admin.post(
        "/import/students/apply",
        json={"students": selected(again), "direction_id": direction_id(admin)},
    ).json()
    assert (repeat["created"], repeat["unchanged"], repeat["accounts"]) == (0, 3, [])


def test_gradebook_matches_by_external_id_and_moves_group(admin: TestClient):
    p = upload(admin, "grades.xlsx", gradebook_xlsx())
    assert p["mapping"]["first_name"] == 0 and p["mapping"]["last_name"] == 1
    assert p["mapping"]["group"] == 4  # «Отдел»
    names = [r["full_name"] for r in p["rows"]]
    assert names == ["Смирнова Ольга", "Фёдоров Олег"]
    admin.post(
        "/import/students/apply",
        json={
            "students": selected(p),
            "direction_id": direction_id(admin),
            "create_accounts": False,
        },
    )

    # Смирнову перевели в другую группу и исправили ФИО – узнаём по индивидуальному номеру.
    wb = Workbook()
    ws = wb.active
    ws.append(["Фамилия", "Имя", "Индивидуальный номер", "Группа"])
    ws.append(["Смирнова-Петрова", "Ольга", "123456", "ПИ-21"])
    buffer = io.BytesIO()
    wb.save(buffer)
    p2 = upload(admin, "moved.xlsx", buffer.getvalue())
    [row] = p2["rows"]
    assert (row["status"], row["existing_group"]) == ("update", "ПИ-23")
    result = admin.post(
        "/import/students/apply", json={"students": selected(p2), "create_accounts": False}
    ).json()
    assert result["updated"] == 1
    students = admin.get("/students").json()
    olga = next(s for s in students if s["external_id"] == "123456")
    groups = {g["id"]: g["name"] for g in admin.get("/groups").json()}
    assert (olga["full_name"], groups[olga["group_id"]]) == ("Смирнова-Петрова Ольга", "ПИ-21")


def test_cp1251_semicolon_and_default_group(admin: TestClient):
    text = "ФИО;Логин\nСидоров Пётр Алексеевич;sidorov_pa\nКузнецова Ирина;kuznetsova\n"
    p = upload(admin, "list.csv", text.encode("cp1251"))
    rows = p["rows"]
    # Сидоров уже есть в ПИ-21, но без группы в файле совпадение по ФИО не ищем.
    assert [(r["full_name"], r["external_id"], r["group"]) for r in rows] == [
        ("Сидоров Пётр Алексеевич", "sidorov_pa", None),
        ("Кузнецова Ирина", "kuznetsova", None),
    ]
    group = next(g for g in admin.get("/groups").json() if g["name"] == "ПИ-21")
    no_group = admin.post("/import/students/apply", json={"students": selected(p)})
    assert no_group.status_code == 400 and "группу по умолчанию" in no_group.json()["detail"]
    result = admin.post(
        "/import/students/apply",
        json={"students": selected(p), "default_group_id": group["id"]},
    ).json()
    assert result["created"] == 2
    assert [a["username"] for a in result["accounts"]] == ["sidorov_pa", "kuznetsova"]


def test_existing_student_matched_by_name_and_group(admin: TestClient):
    text = "ФИО,Группа,Email\nИванов Иван Иванович,ПИ-21,ivanov@stud.example.ru\n"
    [row] = upload(admin, "list.csv", text.encode())["rows"]
    assert row["status"] == "update" and row["existing_group"] == "ПИ-21"
    result = admin.post(
        "/import/students/apply", json={"students": selected({"rows": [row]})}
    ).json()
    # У Иванова из демо-данных уже есть учётка student1 – новую не создаём.
    assert (result["created"], result["updated"], result["accounts"]) == (0, 1, [])


def test_manual_mapping_and_problems(admin: TestClient):
    text = "a,b,c\nКоролёв Сергей,ПИ-21,x1\n,ПИ-21,x2\nЛебедев Иван,ПИ-21,x1\n"
    p = upload(admin, "raw.csv", text.encode(), {"full_name": 0, "group": 1, "external_id": 2})
    problems = [r["problems"] for r in p["rows"]]
    assert problems == [[], ["нет ФИО"], ["идентификатор СДО повторяется в файле"]]


def test_unsupported_and_validation(admin: TestClient, student: TestClient):
    bad = admin.post("/import/students/preview", files={"file": ("a.xls", b"\xd0\xcf")})
    assert bad.status_code == 400
    empty = admin.post("/import/students/preview", files={"file": ("a.csv", b"\n\n")})
    assert empty.status_code == 400
    wrong_mapping = admin.post(
        "/import/students/preview",
        files={"file": ("a.csv", b"x,y\n1,2\n")},
        data={"mapping": "[1]"},
    )
    assert wrong_mapping.status_code == 400
    new_group = admin.post(
        "/import/students/apply", json={"students": [{"full_name": "Тест", "group": "НОВАЯ-1"}]}
    )
    assert new_group.status_code == 400 and "направление" in new_group.json()["detail"]
    forbidden = student.post("/import/students/apply", json={"students": [{"full_name": "x"}]})
    assert forbidden.status_code == 403


def test_name_key():
    from app.services.student_import import name_key

    assert name_key("Фёдоров Олег Петрович") == name_key("олег петрович ФЕДОРОВ")
    assert name_key("Иванов Иван") != name_key("Иванов Иван Иванович")


def test_program_column_sets_direction_of_new_groups(admin: TestClient):
    other = admin.post(
        "/directions", json={"code": "27.03.04", "name": "Управление в технических системах"}
    )
    assert other.status_code == 201, other.text
    csv = (
        "ФИО,Группа,Образовательная программа\n"
        "Орлов Олег Олегович,УТС-24,27.03.04 Управление в технических системах\n"
        "Белова Вера Павловна,ПИ-24,Программная инженерия\n"
    )
    p = upload(admin, "students.csv", csv.encode())
    assert p["mapping"]["program"] == 2
    rows = [{k: r[k] for k in ("full_name", "group", "program")} for r in p["rows"]]
    result = admin.post("/import/students/apply", json={"students": rows, "create_accounts": False})
    assert result.status_code == 200, result.text
    groups = {g["name"]: g["direction_id"] for g in admin.get("/groups").json()}
    directions = {d["code"]: d["id"] for d in admin.get("/directions").json()}
    assert groups["УТС-24"] == directions["27.03.04"]
    assert groups["ПИ-24"] == directions["09.03.04"]
