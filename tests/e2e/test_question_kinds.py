"""Задания на соответствие, последовательность и открытого типа в интерфейсе."""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import assign_new_test, login

pytestmark = pytest.mark.e2e


def test_editor_creates_matching_question(admin_page: Page):
    page = admin_page
    page.click("nav >> text=Банк вопросов")
    page.click("button:text-is('Новый вопрос')")
    form = page.locator("form.edit-form")
    form.get_by_label("Тип задания").select_option("matching")
    form.get_by_label("Уровень сложности").select_option("advanced")
    form.locator("textarea").fill("Соотнесите протоколы и порты:")
    rows = form.locator(".pair-row")
    expect(rows).to_have_count(4)
    for i, (left, right) in enumerate(
        [("SSH", "22"), ("HTTP", "80"), ("HTTPS", "443"), ("FTP", "21")]
    ):
        rows.nth(i).locator("input").nth(0).fill(left)
        rows.nth(i).locator("input").nth(1).fill(right)
    form.locator("button:text-is('+ лишний элемент')").click()
    form.locator("input[placeholder='Лишний элемент правого столбца']").fill("25")
    form.locator("button:text-is('Сохранить')").click()

    row = page.locator("tr", has=page.locator("td:has-text('Соотнесите протоколы и порты')"))
    expect(row).to_contain_text("На установление соответствия")
    expect(row).to_contain_text("повышенный")
    row.locator("text=Изменить").click()
    expect(page.locator("form.edit-form .pair-row").nth(2).locator("input").nth(1)).to_have_value(
        "443"
    )


def test_student_answers_every_kind(admin_page: Page, new_page):
    page = admin_page
    questions = page.request.get("/questions").json()
    markers = {"sequence": "nginx", "matching": "портами", "open": "Учётная запись"}
    typed = {
        q["kind"]: q for q in questions if q["kind"] in markers and markers[q["kind"]] in q["text"]
    }
    assert set(typed) == {"sequence", "matching", "open"}
    # ОПК-5: 20 вопросов в банке, по 20 на вариант — в тест попадут все, включая три новых типа.
    assign_new_test(page, "Все типы", ["ОПК-5"], per_competency=20)

    student = new_page()
    login(student, "student1", "student123")
    student.click("text=Пройти")
    expect(student.locator(".question")).to_have_count(20)

    def block(question: dict):
        return student.locator(
            ".question", has=student.locator("p", has_text=question["text"][:30])
        )

    block(typed["open"]).get_by_label("Ответ").fill("ROOT")

    seq = typed["sequence"]
    items = block(seq).locator(".seq-list li")
    for target, option in enumerate(seq["options"]):  # пузырьком поднимаем нужный элемент
        while True:
            texts = [t.strip() for t in items.locator("span").all_inner_texts()]
            pos = texts.index(option["text"])
            if pos == target:
                break
            items.nth(pos).get_by_role("button", name=re.compile("^Поднять")).click()

    match = typed["matching"]
    by_id = {o["id"]: o for o in match["options"]}
    for left in (o for o in match["options"] if o["match_id"]):
        select = block(match).get_by_label(f"Пара для «{left['text']}»")
        label = next(
            t
            for t in select.locator("option").all_inner_texts()
            if t.endswith(f". {by_id[left['match_id']]['text']}")
        )
        select.select_option(label=label)

    student.click("text=Сдать тест")
    expect(student.locator(".score")).to_have_text("3 / 20")  # три новых задания — верно
