import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import login, logout, open_section
from tests.import_samples import fund_docx, matrix_xlsx, plan_xlsx, rpd_docx

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
    open_section(page, "Подготовка", "Загрузить документ")
    upload(page, "rpd.docx", rpd_docx(), "application/octet-stream")
    expect(page.locator("text=найдено компетенций")).to_be_visible()
    page.click("text=Импортировать выбранные")
    expect(page.locator("text=Импорт выполнен")).to_be_visible()

    open_section(page, "Подготовка", "Загрузить документ")
    upload(page, "matrix.xlsx", matrix_xlsx(), "application/octet-stream")
    expect(page.locator("text=найдено компетенций")).to_be_visible()
    page.click("text=Импортировать выбранные")
    expect(page.locator("text=Импорт выполнен")).to_be_visible()

    page.click("text=Открыть компетенции")
    expect(page.locator("td:text-is('ОПК-2')")).to_be_visible()
    expect(page.locator("td:text-is('УК-2')")).to_be_visible()
    page.click(".subnav >> text=Дисциплины")
    expect(page.locator("td:text-is('Базы данных')")).to_be_visible()


def test_plan_import(admin_page: Page):
    page = admin_page
    open_section(page, "Подготовка", "Загрузить документ")
    upload(page, "09.03.01_2023.plx.xlsx", plan_xlsx(), "application/octet-stream")
    expect(page.locator("text=учебный план 09.03.01 Информатика")).to_be_visible()
    expect(page.locator("text=Будет создан новый учебный план.")).to_be_visible()
    page.click("button:text-is('Загрузить учебный план')")
    expect(page.locator("text=Учебный план загружен")).to_be_visible()

    # Дисциплины открываются по загруженному направлению, в порядке плана, со статусом.
    page.click("text=Открыть дисциплины")
    chosen = page.get_by_label("Учебный план").locator("option:checked")
    expect(chosen).to_have_text(
        "09.03.01 Информатика и вычислительная техника, "
        "Программное обеспечение робототехнических систем, 2023"
    )
    first = page.locator("tbody tr, table tr").nth(1)
    expect(first).to_contain_text("Б1.О.01.01")
    row = page.locator("tr", has=page.locator("td", has_text="Сети"))
    expect(row.locator(".badge.kind")).to_have_text("по выбору")
    expect(row.locator(".chip")).to_have_text(["ПК-1"])


def test_fund_import(admin_page: Page):
    page = admin_page
    open_section(page, "Банк вопросов")
    page.click("text=Загрузить из ФОС (Word)")
    upload(page, "Архитектура ПО.docx", fund_docx(), "application/octet-stream")
    expect(page.locator("text=Заданий: 5 – новых 4, уже в банке 0, не разобрано 1")).to_be_visible()
    page.click("details summary:text-is('Задания')")
    expect(page.locator("td", has_text="Класс → Шаблон для создания объектов.")).to_be_visible()
    page.click("text=Загрузить новые вопросы (4)")
    expect(page.locator(".success")).to_contain_text("Добавлено вопросов: 4")

    page.get_by_label("Дисциплина").select_option(label="Архитектура ПО")
    expect(page.locator("text=Вопросов: 4")).to_be_visible()


def test_student_import_and_first_login(new_page):
    page = new_page(accept_downloads=True)
    login(page, "admin", "admin123")
    open_section(page, "Люди", "Загрузить список")
    expect(page.locator("text=Загрузите список студентов")).to_be_visible()
    upload(page, "participants.csv", SDO_PARTICIPANTS.encode(), "text/csv")
    # Иванов уже есть в группе, преподаватель не студент – новых один
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


def test_plan_import_asks_about_plan_with_empty_fields(admin_page: Page):
    page = admin_page
    body = {"code": "09.03.01", "name": "ИВТ вручную"}
    assert page.request.post("/directions", data=body, headers={"X-Requested-With": "fetch"}).ok
    open_section(page, "Подготовка", "Загрузить документ")
    upload(page, "plan.plx.xlsx", plan_xlsx(), "application/octet-stream")
    save = page.locator("button:text-is('Загрузить учебный план')")
    expect(save).to_be_disabled()
    page.get_by_label("Создать новый учебный план").check()
    expect(save).to_be_enabled()
    expect(page.get_by_label("Создать новый учебный план")).to_be_checked()
    save.click()
    expect(page.locator("text=Учебный план создан")).to_be_visible()
