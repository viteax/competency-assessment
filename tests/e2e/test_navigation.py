"""Адрес экрана в строке браузера: «Назад», обновление страницы и ссылки на экран;
черновик ответов студента переживает обновление страницы и уход в меню."""

import re
from urllib.parse import quote

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import assign_new_test, login, logout, open_section

pytestmark = pytest.mark.e2e


def address(path: str) -> re.Pattern:
    """Адрес экрана в строке браузера: русские буквы в нём закодированы."""
    return re.compile(re.escape(f"#/{quote(path)}") + "$")


def test_address_back_and_reload(admin_page: Page):
    page = admin_page
    expect(page).to_have_url(re.compile(r"#/home$"))

    open_section(page, "Люди", "Студенты")
    expect(page).to_have_url(address("people/студенты"))
    open_section(page, "Система")
    expect(page.locator("h1")).to_have_text("Система")

    page.go_back()
    expect(page.locator("h1")).to_have_text("Люди")
    expect(page.locator(".subnav .active")).to_have_text("Студенты")

    page.reload()
    expect(page.locator(".subnav .active")).to_have_text("Студенты")
    expect(page.locator("nav .active")).to_have_text("Люди")

    # Переход по вкладке – тоже шаг истории.
    page.go_back()
    expect(page.locator(".subnav .active")).to_have_text("Группы")
    page.go_back()
    expect(page).to_have_url(re.compile(r"#/home$"))
    expect(page.locator("h1")).to_have_text("Главная")


def test_link_to_tab_and_unknown_address(admin_page: Page):
    page = admin_page
    page.goto("/ui/#/people/студенты")
    expect(page.locator(".subnav .active")).to_have_text("Студенты")
    page.goto("/ui/#/no-such-screen")
    expect(page).to_have_url(re.compile(r"#/home$"))


def test_logout_forgets_address(admin_page: Page):
    page = admin_page
    open_section(page, "Система", "Журнал")
    logout(page)
    login(page, "student1", "student123")
    expect(page).to_have_url(re.compile(r"#/tests$"))


def test_answers_survive_reload_and_menu(admin_page: Page):
    page = admin_page
    # Все 10 доступных заданий ПК-2: в тесте точно есть все три типа.
    assign_new_test(page, "Черновик", ["ПК-2"], per_competency=10)
    logout(page)
    login(page, "student1", "student123")
    page.click("text=Пройти")
    expect(page).to_have_url(re.compile(r"#/test/\d+$"))

    page.locator(".question input[type=text]").first.fill("мой ответ")
    first_select = page.locator(".question select").first
    first_select.select_option(index=1)
    chosen = first_select.input_value()
    sequence = page.locator(".seq-list").first
    sequence.locator("button[title=Ниже]").first.click()
    order = sequence.locator("li > span").all_inner_texts()
    expect(page.locator("text=Ответы сохранены")).to_be_visible()

    page.reload()
    expect(page.locator(".question input[type=text]").first).to_have_value("мой ответ")
    expect(page.locator(".question select").first).to_have_value(chosen)
    assert page.locator(".seq-list").first.locator("li > span").all_inner_texts() == order

    # Уход в меню до автосохранения: изменение всё равно сохранится.
    page.locator(".question input[type=text]").first.fill("исправленный ответ")
    page.click("nav >> text=Мои результаты")
    expect(page.locator("h1")).to_have_text("Мои результаты")
    page.go_back()
    expect(page.locator(".question input[type=text]").first).to_have_value("исправленный ответ")

    page.click("text=Сдать тест")
    expect(page.locator(".score")).to_be_visible()
    expect(page).to_have_url(re.compile(r"#/tests$"))
    page.reload()
    expect(page.locator("h1")).to_have_text("Мои тесты")
