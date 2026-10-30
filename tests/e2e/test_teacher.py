"""Преподаватель: кабинет с квотами, составление вопроса, ФОМ; админ закрепляет дисциплины."""

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import login, open_section

pytestmark = pytest.mark.e2e


def test_teacher_composes_questions(new_page):
    page = new_page(accept_downloads=True)
    login(page, "teacher", "teacher123")
    expect(page.locator("h1")).to_have_text("Мои дисциплины")
    expect(page.locator("#who")).to_contain_text("Морозов Сергей Николаевич (преподаватель)")
    card = page.locator(".card", has=page.locator("h2:text-is('Технологии программирования')"))
    expect(card).to_contain_text("Сделано 20 из 25")
    expect(card).to_contain_text("осталось 5")
    expect(page.locator("nav button")).to_have_count(1)  # только «Мои дисциплины»

    with page.expect_download() as download:
        card.locator("a:text-is('ФОМ с ответами (Word)')").click()
    assert download.value.suggested_filename == "ФОМ – Технологии программирования – ключ.docx"

    card.locator("button:text-is('Составлять вопросы')").click()
    expect(page.locator("h1")).to_have_text("Технологии программирования")
    page.click("button:text-is('Новый вопрос')")
    form = page.locator("form.edit-form")
    options = [
        o.split(" – ")[0]
        for o in form.get_by_label("Компетенция").locator("option").all_inner_texts()
    ]
    assert options == ["ПК-1", "ПК-2"]  # только компетенции этой дисциплины
    form.get_by_label("Тип задания").select_option("open")
    form.locator("textarea").fill("Команда Git для просмотра истории коммитов – git ________.")
    form.locator("input[placeholder='Правильный ответ']").fill("log")
    form.locator("button:text-is('Сохранить')").click()
    expect(page.locator("td:has-text('просмотра истории коммитов')")).to_be_visible()
    expect(page.locator(".card").first).to_contain_text("Сделано 21 из 25")


def test_admin_adds_teacher_and_assigns_discipline(admin_page: Page, new_page):
    page = admin_page
    open_section(page, "Люди", "Преподаватели")
    page.get_by_label("ФИО преподавателей, по одному на строку").fill(
        "Лебедев Олег Игоревич\nСоколова Анна Петровна"
    )
    page.click("form >> button:text-is('Добавить')")
    row = page.locator(".notice tr", has=page.locator("td:text-is('Лебедев Олег Игоревич')"))
    expect(row).to_contain_text("Лебедев О.И.")
    temp = row.locator("code").nth(1).inner_text()
    expect(page.locator(".notice")).to_contain_text("Соколова А.П.")

    open_section(page, "Подготовка", "Учебный план и преподаватели")
    row = page.locator("tr", has=page.locator("td:text-is('Математика')"))
    row.locator("text=Изменить").click()
    form = page.locator("form.edit-form")
    form.locator("select").nth(1).select_option(label="Лебедев Олег Игоревич")
    form.get_by_label("Вопросов по ОПК-1").fill("4")
    form.get_by_label("Вопросов по УК-1").fill("20")
    form.locator("button:text-is('Сохранить')").click()
    row = page.locator("tr", has=page.locator("td:text-is('Математика')"))
    expect(row).to_contain_text("Лебедев Олег Игоревич")
    expect(row).to_contain_text("УК-1: 20, ОПК-1: 4")

    teacher = new_page()
    login(teacher, "лебедев о.и.", temp)
    expect(teacher.locator("text=Задайте свой пароль")).to_be_visible()
    fields = teacher.locator("input[type=password]")
    fields.nth(0).fill(temp)
    fields.nth(1).fill("Kafedra-2026-pass")
    fields.nth(2).fill("Kafedra-2026-pass")
    teacher.click("button:text-is('Сохранить')")
    card = teacher.locator(".card", has=teacher.locator("h2:text-is('Математика')"))
    expect(card).to_contain_text("Сделано 14 из 24")  # ОПК-1: 4 из 4, УК-1: 10 из 20
