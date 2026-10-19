import re

import pytest
from playwright.sync_api import Locator, Page, expect

from tests.e2e.conftest import assign_new_test

pytestmark = pytest.mark.e2e


def select_prefix(select: Locator, prefix: str) -> None:
    value = select.evaluate(
        "(el, p) => [...el.options].find(o => o.textContent.startsWith(p)).value", prefix
    )
    select.select_option(value)


def row(page: Page, cell: str) -> Locator:
    return page.locator("tr", has=page.locator(f"td:text-is('{cell}')"))


def test_edit_catalogs(admin_page: Page):
    page = admin_page
    assign_new_test(page, "Входной контроль", ["ПК-1"])

    page.click("nav >> text=Справочники")
    page.click(".card >> button:text-is('Добавить')")
    form = page.locator("form.edit-form")
    form.locator("input").nth(0).fill("ПК-3")
    form.locator("select").select_option("ПК")
    form.locator("textarea").fill("Способен проектировать программное обеспечение")
    form.locator("button:text-is('Сохранить')").click()
    row(page, "ПК-3").locator("text=Изменить").click()
    page.locator("form.edit-form textarea").fill("Способен проектировать архитектуру ПО")
    page.locator("form.edit-form button:text-is('Сохранить')").click()
    expect(page.locator("td:text-is('Способен проектировать архитектуру ПО')")).to_be_visible()

    # компетенцию, по которой есть вопросы, удалить нельзя
    row(page, "ПК-1").locator("text=Удалить").click()
    expect(page.locator(".error:has-text('нельзя удалить')")).to_be_visible()

    expect(page.locator(".subnav >> text=Индикаторы")).to_have_count(0)  # не используются

    page.click(".subnav >> text=ТФ ⇒ компетенции")
    row(page, "A/01.3").locator("text=Изменить").click()
    page.locator("form.edit-form label", has_text=re.compile("^ПК-3$")).locator("input").check()
    page.locator("form.edit-form button:text-is('Сохранить')").click()
    expect(page.locator("td:text-is('ОПК-1, ПК-1, ПК-3')")).to_be_visible()


def test_edit_questions(admin_page: Page):
    page = admin_page
    assign_new_test(page, "Входной контроль", ["ПК-1"])

    page.click("nav >> text=Банк вопросов")
    page.click("button:text-is('Новый вопрос')")
    form = page.locator("form.edit-form")
    select_prefix(form.get_by_label("Компетенция"), "ПК-2 ")
    form.locator("textarea").fill("Какая диаграмма UML описывает классы?")
    options = form.locator(".option-row")
    expect(options).to_have_count(4)
    for i, text in enumerate(["Диаграмма классов", "Диаграмма состояний", "Диаграмма потоков"]):
        options.nth(i).locator("input[type=text]").fill(text)
    options.nth(3).locator("button").click()  # лишний пустой вариант
    form.locator("button:text-is('Сохранить')").click()

    question = page.locator("tr", has=page.locator("td:has-text('Какая диаграмма UML')"))
    question.locator("text=Изменить").click()
    page.locator("form.edit-form textarea").fill("Какая диаграмма UML описывает структуру?")
    page.locator("form.edit-form button:text-is('Сохранить')").click()
    edited = page.locator("td:has-text('описывает структуру')")
    expect(edited).to_be_visible()
    page.locator("tr", has=edited).locator("text=Удалить").click()
    expect(edited).to_have_count(0)

    # вопрос, уже вошедший в тест: компетенцию сменить нельзя
    page.locator("tr", has=page.locator("text=в тестах")).first.locator("text=Изменить").click()
    expect(page.locator("text=уже входит в собранные тесты")).to_be_visible()
    form = page.locator("form.edit-form")
    expect(form.get_by_label("Компетенция")).to_be_disabled()
    expect(form.get_by_label("Тип задания")).to_be_disabled()


def test_mastery_threshold_setting(admin_page: Page):
    page = admin_page
    page.click("nav >> text=Справочники")
    page.click(".subnav >> text=Настройки")
    field = page.locator("form input[type=number]")
    expect(field).to_have_value("60")
    field.fill("75")
    page.click("button:text-is('Сохранить')")
    expect(page.locator(".success")).to_contain_text("от 75%")

    page.click("nav >> text=Результаты группы")
    expect(page.locator("text=от 75% верных ответов")).to_be_visible()
    page.reload()
    page.click("nav >> text=Справочники")
    page.click(".subnav >> text=Настройки")
    expect(page.locator("form input[type=number]")).to_have_value("75")
