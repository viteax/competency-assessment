import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import answer_all, assign_new_test, login, logout, open_section

pytestmark = pytest.mark.e2e


def test_wrong_password_shows_error(page: Page):
    login(page, "admin", "bad-password")
    expect(page.locator("[role=alert]")).to_contain_text("неверный")


def test_assign_take_and_review(admin_page: Page):
    page = admin_page
    assign_new_test(page, "Входной контроль", ["ПК-1", "ПК-2"])

    logout(page)
    login(page, "student1", "student123")
    page.click("text=Пройти")
    questions = page.locator(".question")
    expect(questions).to_have_count(6)
    answer_all(page)
    page.click("text=Сдать тест")
    expect(page.locator(".score")).to_be_visible()

    page.click("text=Мои результаты")
    expect(page.locator("text=ПК-1").first).to_be_visible()
    page.click("summary:has-text('трудовые функции профстандарта')")  # подробности свёрнуты
    expect(page.locator("text=ОТФ").first).to_be_visible()

    logout(page)
    login(page, "admin", "admin123")
    open_section(page, "Результаты")
    expect(page.locator("td:has-text('Иванов Иван Иванович')")).to_be_visible()
    page.click("td button:text-is('Иванов Иван Иванович')")  # карточка студента
    expect(page.locator("h1")).to_have_text("Иванов Иван Иванович")
    expect(page.locator("text=ОТФ A").first).to_be_visible()


def test_mobile_has_no_horizontal_scroll(admin_page: Page):
    page = admin_page
    page.set_viewport_size({"width": 390, "height": 800})
    for tab in ["Главная", "Результаты", "Подготовка", "Банк вопросов"]:
        page.click(f"nav >> text={tab}")
        page.wait_for_load_state("networkidle")
        assert page.evaluate("document.documentElement.scrollWidth") <= 390, tab


def test_duplicate_title_and_existing_test(admin_page: Page):
    page = admin_page
    response = page.request.post(
        "/groups",
        data={"name": "ПИ-22", "direction_id": 1},
        headers={"X-Requested-With": "fetch"},
    )
    assert response.ok, response.text()
    page.reload()
    assign_new_test(page, "Входной контроль", ["ПК-1"])

    page.fill("input[placeholder^='любое']", "входной  КОНТРОЛЬ")
    expect(page.locator(".error.small")).to_contain_text("уже есть")
    page.click("button:text-is('Собрать и назначить')")
    expect(page.locator("[role=alert]")).to_contain_text("уже есть")

    page.locator("select").first.select_option(label="ПИ-22")
    page.check("text=Назначить готовый тест")
    page.click("button:text-is('Назначить')")
    expect(page.locator(".success")).to_contain_text("ПИ-22")


def test_slow_screen_does_not_cover_newer_one(admin_page: Page):
    """Пока экран ждёт ответа сервера, пользователь уходит на другой: опоздавший экран не должен
    перерисоваться поверх нового."""
    page = admin_page
    tests = re.compile(r"/tests$")  # вкладка «Новый тест» ждёт этот запрос
    held = []
    page.route(tests, lambda route: held.append(route))

    with page.expect_request(tests):
        open_section(page, "Тесты", "Новый тест")
    open_section(page, "Люди")
    expect(page.locator("h1")).to_have_text("Люди")

    with page.expect_response(tests):
        for route in held:
            route.continue_()
    page.wait_for_timeout(300)  # опоздавший экран отрисовался бы сразу после ответа
    expect(page.locator("h1")).to_have_text("Люди")
