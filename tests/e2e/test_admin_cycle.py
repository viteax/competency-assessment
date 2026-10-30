"""Кабинет администратора по циклу работы: направление в шапке и карточка студента."""

import re
from urllib.parse import quote

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import answer_all, assign_new_test, login, logout, open_section

pytestmark = pytest.mark.e2e

JSON = {"X-Requested-With": "fetch"}


def test_direction_in_header_switches_every_screen(admin_page: Page):
    page = admin_page
    direction = page.request.post(
        "/directions", data={"code": "09.03.05", "name": "Информационные системы"}, headers=JSON
    ).json()
    competency = {
        "direction_id": direction["id"],
        "code": "ПК-9",
        "kind": "ПК",
        "description": "Проверочная компетенция",
    }
    assert page.request.post("/competencies", data=competency, headers=JSON).ok
    page.reload()
    picker = page.locator("#direction").get_by_label("Учебный план")

    open_section(page, "Подготовка", "Компетенции")
    expect(page.locator("td:text-is('ПК-1')")).to_be_visible()
    expect(page.locator("td:text-is('ПК-9')")).to_have_count(0)
    open_section(page, "Банк вопросов")
    expect(page.locator("text=Вопросов: 0")).to_have_count(0)

    picker.select_option(label="09.03.05 Информационные системы")
    expect(page.locator("text=Вопросов: 0")).to_be_visible()  # экран перерисовался
    open_section(page, "Подготовка")
    expect(page.locator("td:text-is('ПК-9')")).to_be_visible()
    expect(page.locator("td:text-is('ПК-1')")).to_have_count(0)

    # Выбор переживает обновление страницы.
    page.reload()
    expect(picker.locator("option:checked")).to_have_text("09.03.05 Информационные системы")
    expect(page.locator("td:text-is('ПК-9')")).to_be_visible()


def test_student_card_opens_from_results_and_by_address(new_page):
    page = new_page()
    login(page, "admin", "admin123")
    assign_new_test(page, "Входной контроль", ["ПК-1", "ПК-2"])
    logout(page)
    login(page, "student1", "student123")
    page.click("text=Пройти")
    answer_all(page)
    page.click("text=Сдать тест")
    expect(page.locator(".score")).to_be_visible()
    logout(page)
    login(page, "admin", "admin123")

    open_section(page, "Результаты")
    page.click("td button:text-is('Иванов Иван Иванович')")
    expect(page.locator("h1")).to_have_text("Иванов Иван Иванович")
    expect(page.locator("h2:has-text('Трудовые функции – Иванов Иван Иванович')")).to_be_visible()
    expect(page.locator("text=ОТФ A").first).to_be_visible()
    assert re.search(rf"#/{quote('results')}/student/\d+$", page.url)

    page.reload()
    expect(page.locator("h1")).to_have_text("Иванов Иван Иванович")
    expect(page.locator("nav .active")).to_have_text("Результаты")
    page.click("text=← Результаты группы")
    expect(page.locator("h1")).to_have_text("Результаты группы")


def test_results_keep_selected_group_after_student_card(admin_page: Page):
    page = admin_page
    response = page.request.post("/groups", data={"name": "ПИ-22", "direction_id": 1}, headers=JSON)
    assert response.ok, response.text()
    page.reload()
    open_section(page, "Результаты")
    group = page.locator("label:text-is('Группа') + select")
    group.select_option(label="ПИ-22")
    student_id = page.request.get("/students").json()[0]["id"]
    page.evaluate(f"location.hash = '#/results/student/{student_id}'")
    expect(page.locator("h2:has-text('ПК → ОТФ')")).to_be_visible()
    page.click("text=← Результаты группы")
    expect(page.locator("h1")).to_have_text("Результаты группы")
    expect(group.locator("option:checked")).to_have_text("ПИ-22")


def test_two_plans_of_one_code_have_their_own_data(admin_page: Page):
    page = admin_page
    plans = [
        page.request.post(
            "/directions",
            data={"code": "11.03.02", "name": "Связь", "plan_year": year},
            headers=JSON,
        ).json()
        for year in (2023, 2026)
    ]
    for plan, code in zip(plans, ("ПК-3", "ПК-6"), strict=True):
        body = {"direction_id": plan["id"], "code": code, "kind": "ПК", "description": "к"}
        assert page.request.post("/competencies", data=body, headers=JSON).ok
    page.reload()
    picker = page.locator("#direction").get_by_label("Учебный план")
    open_section(page, "Подготовка", "Компетенции")

    picker.select_option(label="11.03.02 Связь, 2023")
    expect(page.locator("td:text-is('ПК-3')")).to_be_visible()
    expect(page.locator("td:text-is('ПК-6')")).to_have_count(0)
    picker.select_option(label="11.03.02 Связь, 2026")
    expect(page.locator("td:text-is('ПК-6')")).to_be_visible()
    expect(page.locator("td:text-is('ПК-3')")).to_have_count(0)
