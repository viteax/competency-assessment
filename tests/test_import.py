import pytest
from fastapi.testclient import TestClient

from app.services.competency_import import parse_text
from tests.helpers import by_code
from tests.import_samples import matrix_xlsx, rpd_docx

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# --- разбор текста ----------------------------------------------------------


def test_parse_code_variants():
    doc = parse_text(
        "УК-1. Способен осуществлять поиск информации\n"
        "УК-1.1. Знает методы поиска\n"
        "ИУК-1.2 Умеет анализировать\n"
        "ИД-3.УК-1 Владеет синтезом\n"
        "ИД-1 ОПК-5 Знает основы администрирования\n"
        "ИДК-ПК-2.1: Знает методы тестирования\n"
        "ОПК‑10 – Способен (неразрывный дефис и тире)\n"
        "ПК-3 \u2014 Способен проектировать (длинное тире из документов вуза)\n"
    )
    assert list(doc.competencies) == ["УК-1", "ОПК-5", "ОПК-10", "ПК-2", "ПК-3"]
    uk1 = doc.competencies["УК-1"]
    assert uk1.description == "Способен осуществлять поиск информации"
    assert uk1.indicators == {
        "УК-1.1": "Знает методы поиска",
        "УК-1.2": "Умеет анализировать",
        "УК-1.3": "Владеет синтезом",
    }
    assert doc.competencies["ОПК-5"].indicators == {"ОПК-5.1": "Знает основы администрирования"}
    assert doc.competencies["ОПК-5"].description == ""  # формулировки в тексте нет
    assert doc.competencies["ПК-2"].indicators == {"ПК-2.1": "Знает методы тестирования"}
    assert doc.competencies["ОПК-10"].description == "Способен (неразрывный дефис и тире)"
    assert (
        doc.competencies["ПК-3"].description
        == "Способен проектировать (длинное тире из документов вуза)"
    )


def test_parse_keeps_longest_description_and_ignores_noise():
    doc = parse_text(
        "Код и наименование компетенции\n"
        "ПК-1. Способен разрабатывать программный код\n\n"
        "Формируемые компетенции: ПК-1, ПК-2.\n"
        "ГПК-3 и ПК1 не являются кодами компетенций"
    )
    assert doc.competencies["ПК-1"].description == "Способен разрабатывать программный код"
    assert set(doc.competencies) == {"ПК-1", "ПК-2"}


def test_parse_discipline_name():
    assert parse_text("Рабочая программа дисциплины «Математика»").discipline_name == "Математика"
    assert (
        parse_text('РАБОЧАЯ ПРОГРАММА ДИСЦИПЛИНЫ (МОДУЛЯ) "Базы данных"').discipline_name
        == "Базы данных"
    )
    assert parse_text("Матрица компетенций").discipline_name is None


# --- предпросмотр и сохранение ----------------------------------------------


def preview(admin: TestClient, name: str, data: bytes, mime: str) -> dict:
    response = admin.post(
        "/import/preview", files={"file": (name, data, mime)}, data={"direction_id": "1"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def to_apply(p: dict, **extra) -> dict:
    return {
        "direction_id": p["direction_id"],
        "discipline_name": p["discipline_name"],
        "competencies": [
            {
                "code": c["code"],
                "description": c["description"],
                "indicators": [
                    {"code": i["code"], "description": i["description"]} for i in c["indicators"]
                ],
            }
            for c in p["competencies"]
        ],
        **extra,
    }


@pytest.mark.parametrize("merged", [True, False])
def test_rpd_docx_preview(admin: TestClient, merged: bool):
    p = preview(admin, "rpd.docx", rpd_docx(merged), DOCX)
    assert p["discipline_name"] == "Базы данных" and p["discipline_exists"] is False
    items = {c["code"]: c for c in p["competencies"]}
    assert list(items) == ["ОПК-2", "ПК-1"]

    opk2 = items["ОПК-2"]
    assert opk2["status"] == "new"
    assert opk2["description"].startswith("Способен понимать принципы работы")
    assert [i["code"] for i in opk2["indicators"]] == ["ОПК-2.1", "ОПК-2.2"]

    # ПК-1 уже есть в БД с другой формулировкой и другими индикаторами.
    pk1 = items["ПК-1"]
    assert pk1["status"] == "update"
    assert pk1["existing_description"] == "Способен разрабатывать и отлаживать программный код"
    assert [(i["code"], i["exists"], i["changed"]) for i in pk1["indicators"]] == [
        ("ПК-1.1", True, True),
        ("ПК-1.2", True, True),
        ("ПК-1.3", False, False),
    ]
    assert p["warnings"] == []


def test_apply_creates_links_and_keeps_existing_wording(admin: TestClient):
    p = preview(admin, "rpd.docx", rpd_docx(), DOCX)
    result = admin.post("/import/apply", json=to_apply(p)).json()
    assert result | {"discipline": None} == {
        "created_competencies": 1,  # ОПК-2
        "updated_competencies": 0,  # ПК-1 не перезаписываем без флага
        "created_indicators": 3,  # ОПК-2.1, ОПК-2.2, ПК-1.3
        "updated_indicators": 0,
        "created_discipline": True,
        "linked_competencies": 2,
        "discipline": None,
    }
    assert result["discipline"]["name"] == "Базы данных"

    pk1 = by_code(admin, "ПК-1")
    assert pk1["description"] == "Способен разрабатывать и отлаживать программный код"
    assert [i["code"] for i in pk1["indicators"]] == ["ПК-1.1", "ПК-1.2", "ПК-1.3"]
    opk2 = by_code(admin, "ОПК-2")
    assert opk2["kind"] == "ОПК" and len(opk2["indicators"]) == 2

    # Повторный импорт ничего не меняет.
    again = preview(admin, "rpd.docx", rpd_docx(), DOCX)
    assert again["discipline_exists"] is True
    assert {c["code"]: c["status"] for c in again["competencies"]} == {
        "ОПК-2": "same",
        "ПК-1": "update",  # формулировка в файле всё ещё отличается
    }
    second = admin.post("/import/apply", json=to_apply(again)).json()
    assert (
        second["created_competencies"],
        second["created_indicators"],
        second["linked_competencies"],
    ) == (0, 0, 0)


def test_apply_with_overwrite(admin: TestClient):
    p = preview(admin, "rpd.docx", rpd_docx(), DOCX)
    result = admin.post("/import/apply", json=to_apply(p, overwrite_descriptions=True)).json()
    assert result["updated_competencies"] == 1
    assert result["updated_indicators"] == 2  # ПК-1.1 и ПК-1.2
    assert by_code(admin, "ПК-1")["description"].endswith("на языке высокого уровня")


def test_xlsx_matrix_without_discipline(admin: TestClient):
    p = preview(admin, "matrix.xlsx", matrix_xlsx(), XLSX)
    assert p["discipline_name"] is None
    items = {c["code"]: c for c in p["competencies"]}
    # УК-1 и её индикаторы уже есть, но формулировки индикаторов в файле другие.
    assert items["УК-1"]["status"] == "update"
    assert [(i["exists"], i["changed"]) for i in items["УК-1"]["indicators"]] == [
        (True, True),
        (True, True),
    ]
    assert items["УК-2"]["status"] == "new"
    assert [i["code"] for i in items["УК-2"]["indicators"]] == ["УК-2.1"]
    result = admin.post("/import/apply", json=to_apply(p)).json()
    assert (result["created_competencies"], result["discipline"]) == (1, None)


def test_txt_and_new_competency_without_wording(admin: TestClient):
    text = "Формируемые компетенции: ПК-7.\nПК-7.1 Знает основы DevOps".encode()
    p = preview(admin, "list.txt", text, "text/plain")
    assert p["warnings"] == ["ПК-7: формулировка не найдена – укажите её перед импортом"]
    payload = to_apply(p)
    assert admin.post("/import/apply", json=payload).status_code == 400
    payload["competencies"][0]["description"] = "Способен внедрять практики DevOps"
    assert admin.post("/import/apply", json=payload).json()["created_competencies"] == 1


def test_empty_and_unsupported_files(admin: TestClient):
    empty = preview(admin, "empty.txt", "Пояснительная записка".encode(), "text/plain")
    assert empty["competencies"] == [] and empty["warnings"]
    old = admin.post(
        "/import/preview",
        files={"file": ("rpd.doc", b"\xd0\xcf", "application/msword")},
        data={"direction_id": "1"},
    )
    assert old.status_code == 400 and ".docx" in old.json()["detail"]
    broken = admin.post(
        "/import/preview",
        files={"file": ("rpd.docx", b"not a zip", DOCX)},
        data={"direction_id": "1"},
    )
    assert broken.status_code == 400
    other = admin.post(
        "/import/preview",
        files={"file": ("a.png", b"\x89PNG", "image/png")},
        data={"direction_id": "1"},
    )
    assert other.status_code == 400


def test_apply_validation(admin: TestClient):
    bad_code = {"competencies": [{"code": "ГПК-1", "description": "x"}]}
    assert admin.post("/import/apply", json=bad_code).status_code == 422
    foreign = {
        "competencies": [{"code": "ПК-1", "indicators": [{"code": "ПК-2.1", "description": "x"}]}]
    }
    assert admin.post("/import/apply", json=foreign).status_code == 422


def test_import_requires_admin(student: TestClient):
    response = student.post("/import/preview", files={"file": ("a.txt", b"x", "text/plain")})
    assert response.status_code == 403
