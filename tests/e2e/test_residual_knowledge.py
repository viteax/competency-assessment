"""Сценарий Лариошиной: тест на остаточные знания по семестру, варианты, вкладка «Тесты»."""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import login, logout, open_section

pytestmark = pytest.mark.e2e


def test_semester_variants_and_tests_tab(admin_page: Page, new_page):
    page = admin_page
    open_section(page, "Тесты", "Новый тест")
    expect(page.locator("text=Завершены до")).to_be_visible()

    # Во 2-м семестре проверять нечего: математику и программирование ещё изучают.
    page.get_by_label("Семестр").fill("2")
    page.get_by_label("Семестр").dispatch_event("change")
    expect(page.locator("text=Ни одна дисциплина ещё не завершена")).to_be_visible()

    page.get_by_label("Семестр").fill("5")
    page.get_by_label("Семестр").dispatch_event("change")
    expect(page.locator("h3:text-is('Завершены до 5-го семестра')")).to_be_visible()
    expect(page.locator("text=Ещё изучаются или впереди")).to_contain_text(
        "Тестирование программного обеспечения"
    )

    page.locator("label", has_text=re.compile(r"^ОПК-5 ")).locator("input").check()
    # Вариантов по умолчанию – по числу студентов группы (3).
    expect(page.get_by_label("Вариантов")).to_have_value("3")
    page.get_by_label("Вопросов на компетенцию").fill("7")
    expect(page.locator(".notice")).to_contain_text("3 варианта")
    expect(page.locator(".notice")).to_contain_text("частично пересекаются")
    page.get_by_label("Вопросов на компетенцию").fill("25")
    expect(page.locator(".notice")).to_contain_text("ОПК-5 – 20 из 25")
    expect(page.locator("button:text-is('Собрать и назначить')")).to_be_disabled()
    page.get_by_label("Вопросов на компетенцию").fill("5")
    page.get_by_label("Вариантов").fill("4")
    expect(page.locator(".notice")).to_contain_text("4 варианта по 5 вопросов")
    expect(page.locator(".notice")).to_contain_text("Варианты не пересекаются")
    page.fill("input[placeholder^='любое']", "Остаточные знания")
    page.click("button:text-is('Собрать и назначить')")
    expect(page.locator(".success")).to_contain_text("4 варианта по 5 вопр.")
    logout(page)

    # Двое студентов открывают тест – у них разные варианты.
    seen = []
    for name in ["student1", "student2"]:
        student = new_page()
        login(student, name, "student123")
        student.click("text=Пройти")
        questions = student.locator(".question")
        expect(questions).to_have_count(5)
        # Вопрос узнаём по всему содержимому без номера и порядка строк: у заданий на
        # соответствие формулировка общая, а элементы показываются вперемешку.
        texts = questions.all_inner_texts()
        seen.append({"\n".join(sorted(re.sub(r"^\d+\. ", "", t).splitlines())) for t in texts})
    assert not seen[0] & seen[1]

    login(page, "admin", "admin123")
    open_section(page, "Тесты", "Все тесты")
    page.click("text=Открыть")
    expect(page.locator("h3:text-is('Варианты (4)')")).to_be_visible()
    expect(page.locator("text=Варианты не пересекаются по вопросам")).to_be_visible()
    group_row = page.locator("tr", has=page.locator("td:text-is('ПИ-21')"))
    expect(group_row).to_contain_text("уже проходят")
    expect(page.locator("button:text-is('Удалить тест')")).to_be_disabled()


def test_unassign_and_delete_untouched_test(admin_page: Page):
    page = admin_page
    open_section(page, "Тесты", "Новый тест")
    page.locator("label", has_text=re.compile(r"^ОПК-1 ")).locator("input").check()
    page.fill("input[placeholder^='любое']", "Черновик")
    page.click("button:text-is('Собрать и назначить')")
    expect(page.locator(".success")).to_be_visible()

    open_section(page, "Тесты", "Все тесты")
    page.click("text=Открыть")
    page.click("text=Снять назначение")
    expect(page.locator("text=Пока никому не назначен.")).to_be_visible()
    page.click("button:text-is('Удалить тест')")
    expect(page.locator("text=Тестов пока нет")).to_be_visible()


def test_curriculum_and_group_start_year(admin_page: Page):
    page = admin_page
    open_section(page, "База", "Учебный план")
    row = page.locator("tr", has=page.locator("td:text-is('Математика')"))
    expect(row).to_contain_text("1–2")
    page.click(".subnav >> text=Группы")
    expect(page.locator("tr", has=page.locator("td:text-is('ПИ-21')"))).to_contain_text("2024")
