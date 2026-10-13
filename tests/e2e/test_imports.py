import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import login, logout
from tests.import_samples import matrix_xlsx, rpd_docx

pytestmark = pytest.mark.e2e

SDO_PARTICIPANTS = """\
Имя / Фамилия,Адрес электронной почты,Роли,Группы,Последний доступ к курсу
Иван Иванович Иванов,ivanov@stud.example.ru,Студент,ПИ-21,1 день
Мария Олеговна Новикова,novikova@stud.example.ru,Студент,ПИ-21,2 дня
Анна Викторовна Преподавателева,teacher@example.ru,Преподаватель,,сегодня
"""


def upload(page: Page, name: str, content: bytes, mime: str) -> None:
    page.set_input_files("input[type=file]", {"name": name, "mimeType": mime, "buffer": content})
    page.click("text=Разобрать файл")


def test_competency_import(admin_page: Page):
    page = admin_page
    page.click("nav >> text=Импорт")
    upload(page, "rpd.docx", rpd_docx(), "application/octet-stream")
    expect(page.locator("text=найдено компетенций")).to_be_visible()
    page.click("text=Импортировать выбранные")
    expect(page.locator("text=Импорт выполнен")).to_be_visible()

    page.click("nav >> text=Импорт")
    upload(page, "matrix.xlsx", matrix_xlsx(), "application/octet-stream")
    expect(page.locator("text=найдено компетенций")).to_be_visible()
    page.click("text=Импортировать выбранные")
    expect(page.locator("text=Импорт выполнен")).to_be_visible()

    page.click("text=Открыть справочники")
    expect(page.locator("td:text-is('ОПК-2')")).to_be_visible()
    expect(page.locator("td:text-is('УК-2')")).to_be_visible()
    page.click(".subnav >> text=Дисциплины")
    expect(page.locator("td:text-is('Базы данных')")).to_be_visible()


def test_student_import_and_first_login(new_page):
    page = new_page(accept_downloads=True)
    login(page, "admin", "admin123")
    page.click("nav >> text=Импорт")
    page.click(".subnav >> text=Студенты (выгрузка СДО)")
    expect(page.locator("text=Загрузите список студентов")).to_be_visible()
    upload(page, "participants.csv", SDO_PARTICIPANTS.encode(), "text/csv")
    # Иванов уже есть в группе, преподаватель не студент — новых один
    expect(page.locator("td:has-text('Новикова')")).to_be_visible()
    page.click("text=Импортировать выбранных")
    expect(page.locator("text=Импорт выполнен")).to_be_visible()

    with page.expect_download() as download:
        page.click("text=Скачать логины и пароли (CSV)")
    rows = open(download.value.path(), encoding="utf-8-sig").read().splitlines()
    novikova = next(r for r in rows if "novikova" in r).split(";")
    password = novikova[3].strip('"')

    logout(page)
    login(page, "novikova", password)
    expect(page.locator("text=Задайте свой пароль")).to_be_visible()
