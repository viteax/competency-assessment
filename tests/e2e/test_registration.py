import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import login, logout, open_section

pytestmark = pytest.mark.e2e


def register(page: Page, group: str, full_name: str, password: str) -> None:
    page.goto("/")
    page.click("button:text-is('Зарегистрироваться')")
    page.get_by_label("Группа").select_option(label=group)
    page.get_by_label("ФИО полностью").fill(full_name)
    fields = page.locator("input[type=password]")
    fields.nth(0).fill(password)
    fields.nth(1).fill(password)
    page.click("form button.primary:text-is('Зарегистрироваться')")


def test_student_registers_by_full_name(admin_page: Page):
    page = admin_page
    open_section(page, "Студенты", "Список по группам")
    form = page.locator("form", has_text="Добавить студента")
    form.locator("input").nth(0).fill("Зайцева Ольга Петровна")
    form.locator("button:text-is('Добавить')").click()
    expect(page.locator(".notice")).to_contain_text("зарегистрируется сам")
    logout(page)

    register(page, "ПИ-21", "Петров Пётр Петрович", "olga-own-pass")
    expect(page.locator("[role=alert]")).to_contain_text("нет в списке группы")

    register(page, "ПИ-21", "зайцева  ольга петровна", "olga-own-pass")
    expect(page.locator("h1:text-is('Мои тесты')")).to_be_visible()

    logout(page)
    login(page, "Зайцева Ольга Петровна", "olga-own-pass")
    expect(page.locator("h1:text-is('Мои тесты')")).to_be_visible()

    logout(page)
    register(page, "ПИ-21", "Зайцева Ольга Петровна", "another-pass")
    expect(page.locator("[role=alert]")).to_contain_text("уже")

    page.click("text=Уже есть учётная запись")
    login(page, "admin", "admin123")
    open_section(page, "Студенты", "Список по группам")
    student = page.locator("tr", has=page.locator("td:text-is('Зайцева Ольга Петровна')"))
    expect(student).to_contain_text("создана")
