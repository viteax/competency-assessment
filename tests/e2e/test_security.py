import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import login, logout

pytestmark = pytest.mark.e2e


def test_session_cookie_is_not_readable_by_scripts(admin_page: Page):
    assert "session" not in admin_page.evaluate("document.cookie")
    assert admin_page.evaluate("localStorage.getItem('token')") is None


def test_temporary_password_lifecycle(admin_page: Page):
    page = admin_page
    page.click("nav >> text=Студенты")
    form = page.locator("form", has_text="Добавить студента")
    form.locator("input").nth(0).fill("Орлова Вера Игоревна")  # ФИО
    form.locator("input").nth(1).fill("orlova")  # логин
    form.locator("button:text-is('Добавить')").click()
    expect(page.locator(".notice")).to_contain_text("временный пароль")
    temp = re.search(r"временный пароль (\S+)", page.inner_text(".notice")).group(1)

    logout(page)
    login(page, "orlova", temp)
    expect(page.locator("text=Задайте свой пароль")).to_be_visible()
    fields = page.locator("input[type=password]")
    fields.nth(0).fill(temp)
    fields.nth(1).fill("vera-own-pass")
    fields.nth(2).fill("vera-own-pass")
    page.click("button:text-is('Сохранить')")
    expect(page.locator("h1:text-is('Мои тесты')")).to_be_visible()

    logout(page)
    login(page, "admin", "admin123")
    page.click("nav >> text=Студенты")
    student = page.locator("tr", has=page.locator("td:text-is('Орлова Вера Игоревна')"))
    student.locator("text=Сбросить пароль").click()
    expect(page.locator(".notice")).to_contain_text("временный пароль")

    page.click("nav >> text=Журнал")
    expect(page.locator("td:has-text('reset-password')").first).to_be_visible()

    # после сброса старый пароль не подходит
    logout(page)
    login(page, "orlova", "vera-own-pass")
    expect(page.locator("[role=alert]")).to_contain_text("неверный")


def test_password_guessing_is_slowed_down(page: Page):
    for _ in range(6):
        login(page, "student1", "wrong-pass")
        expect(page.locator("[role=alert]")).not_to_be_empty()
    expect(page.locator("[role=alert]")).to_contain_text("следующая попытка через")
