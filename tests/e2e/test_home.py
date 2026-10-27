"""Главная администратора и разделы с вкладками."""

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import open_section

pytestmark = pytest.mark.e2e


def test_admin_lands_on_home_with_key_facts(admin_page: Page):
    page = admin_page
    expect(page.locator("h1")).to_have_text("Главная")
    expect(page.locator(".tile", has_text="студента")).to_contain_text("с учётной записью – 3")
    expect(page.locator(".tile", has_text="вопросов в банке")).to_contain_text("40 из 45")  # квоты
    expect(page.locator("h2:text-is('Вопросы от преподавателей')")).to_be_visible()
    expect(page.locator("text=Осталось разработать 5 вопросов")).to_be_visible()

    # «Требует внимания» ведёт прямо туда, где это исправить.
    item = page.locator(".attention li", has_text="Не закреплены за преподавателем")
    item.locator("button").click()
    expect(page.locator("h1")).to_have_text("Справочники")
    expect(page.locator(".subnav .active")).to_have_text("Учебный план")
    expect(page.locator("nav .active")).to_have_text("Справочники")

    page.click("nav >> text=Главная")
    page.click("button:text-is('Собрать и назначить тест')")
    expect(page.locator(".subnav .active")).to_have_text("Новый тест")
    expect(page.locator("text=Завершены до")).to_be_visible()


def test_menu_is_short_and_in_work_order(admin_page: Page):
    items = admin_page.locator("nav button").all_inner_texts()
    assert items == [
        "Главная",
        "Тесты",
        "Результаты",
        "Банк вопросов",
        "Студенты",
        "Справочники",
        "Журнал",
    ]


def test_clicking_open_tab_keeps_typed_text(admin_page: Page):
    page = admin_page
    open_section(page, "Студенты", "Список по группам")
    name = page.locator("form", has_text="Добавить студента").locator("input").first
    name.fill("Орлова Вера Игоревна")
    page.click(".subnav >> text=Список по группам")
    page.wait_for_timeout(300)
    expect(name).to_have_value("Орлова Вера Игоревна")
