"""Порядок кодов как в ФГОС: УК, ОПК, ПК, номера по числу, а не по строке."""

from fastapi.testclient import TestClient

from app.services.common import code_key


def test_code_key_orders_like_fgos():
    codes = ["ОПК-10", "ПК-2", "УК-6", "ОПК-2", "УК-1.10", "УК-1.2", "ПК-10", "ОПК-1"]
    assert sorted(codes, key=code_key) == [
        "УК-1.2", "УК-1.10", "УК-6", "ОПК-1", "ОПК-2", "ОПК-10", "ПК-2", "ПК-10",
    ]  # fmt: skip


def test_competency_list_puts_opk_2_before_opk_10(admin: TestClient):
    for code in ["ОПК-10", "ОПК-11"]:
        created = admin.post(
            "/competencies", json={"code": code, "kind": "ОПК", "description": "новая"}
        )
        assert created.status_code == 201, created.text
    codes = [c["code"] for c in admin.get("/competencies").json()]
    assert codes == sorted(codes, key=code_key)
    opk = [c for c in codes if c.startswith("ОПК-")]
    assert opk[-2:] == ["ОПК-10", "ОПК-11"] and len(opk) > 2  # однозначные номера – раньше
