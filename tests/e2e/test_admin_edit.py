import re

import pytest
from playwright.sync_api import Locator, Page, expect

from tests.e2e.conftest import answer_all, assign_new_test, login, logout, open_section

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

    open_section(page, "База", "Компетенции")
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
    kinds = form.get_by_label("Тип задания").locator("option").all_inner_texts()
    assert kinds == [
        "На установление соответствия",
        "На установление последовательности",
        "Открытого типа",
    ]  # выбора одного ответа нет: кафедра использует три типа заданий
    form.get_by_label("Тип задания").select_option(label="Открытого типа")
    form.locator("textarea").fill("Какая диаграмма UML описывает классы?")
    form.locator("button:text-is('+ ещё вариант ответа')").click()
    options = form.locator(".option-row")
    expect(options).to_have_count(2)
    options.nth(0).locator("input[type=text]").fill("Диаграмма классов")
    options.nth(1).locator("button").click()  # лишний пустой вариант
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
    assign_new_test(page, "Порог", ["ПК-1"])
    logout(page)
    login(page, "student1", "student123")  # порог виден в результатах, когда они есть
    page.click("text=Пройти")
    answer_all(page)
    page.click("text=Сдать тест")
    expect(page.locator(".score")).to_be_visible()
    logout(page)
    login(page, "admin", "admin123")

    open_section(page, "База", "Настройки")
    field = page.locator("form input[type=number]")
    expect(field).to_have_value("60")
    field.fill("75")
    page.click("button:text-is('Сохранить')")
    expect(page.locator(".success")).to_contain_text("от 75%")

    open_section(page, "Результаты", "По группе")
    expect(page.locator("text=компетенция сформирована (от 75% верных")).to_be_visible()
    page.reload()
    open_section(page, "База", "Настройки")
    expect(page.locator("form input[type=number]")).to_have_value("75")
