"""Таблицы компетенций в PDF: колонки не перемешиваются.

tests/samples/opop_tables.pdf – страницы настоящей ОПОП: таблица УК, где ячейка
переносится на следующую страницу, абзац по ширине между таблицами и таблица ПК
с колонками задач, объектов и профстандартов по бокам.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.services.competency_import import extract_text, parse_text

SAMPLE = (Path(__file__).parent / "samples" / "opop_tables.pdf").read_bytes()


def parsed():
    return parse_text(extract_text("opop.pdf", SAMPLE)).competencies


def test_cell_continued_on_next_page_is_joined():
    c = parsed()
    # «…для достижения поставленной» | колонтитул | «цели» – на следующей странице.
    assert c["УК-3"].description.endswith("командную стратегию для достижения поставленной цели")
    assert (
        c["УК-3"]
        .indicators["УК-3.1"]
        .endswith("нравственных отношений в рабочем коллективе (группе)")
    )
    # Строка таблицы ПК-3 продолжается на странице, где есть только коды индикаторов.
    assert c["ПК-3"].description.endswith(
        "в соответствии с имеющимися стандартами и техническими условиями"
    )
    assert c["ПК-3"].indicators["ПК-3.3"].endswith("мехатронных и робототехнических систем")


def test_neighbour_columns_headers_and_page_numbers_stay_out():
    c = parsed()
    texts = [t for comp in c.values() for t in [comp.description, *comp.indicators.values()]]
    assert len(c) >= 10 and len(texts) > 30
    for junk in ["1486", "40.011", "Специалист по", "Командная работа", "Коммуникация",
                 "общепрофессиональной компетенции", "15.04.06"]:  # fmt: skip
        assert not [t for t in texts if junk in t], junk
    assert c["УК-6"].description.endswith("на основе самооценки")
    assert c["ПК-1"].description == (
        "Способен проводить анализ технологических и производственных процессов для выявления "
        "операций, подлежащих роботизации"
    )
    assert (
        c["ПК-1"].indicators["ПК-1.3"]
        == "Владеет навыками моделирования в рамках процессного подхода"
    )
    # Перенос по дефису внутри ячейки склеивается без пробела.
    assert "социально-психологические" in c["УК-3"].indicators["УК-3.1"]


def test_case_and_final_dot_are_not_a_change(admin: TestClient):
    # В ОПОП ПК-5 записана со строчной («способностью к…») – берем с прописной.
    pk5 = parsed()["ПК-5"]
    assert pk5.description.startswith("Способностью к подготовке технического задания")
    # В базе та же компетенция, только со строчной буквы и с точками в конце.
    created = admin.post(
        "/competencies",
        json={
            "code": "ПК-5",
            "kind": "ПК",
            "description": pk5.description.lower() + ".",
            "indicators": [{"code": k, "description": v + "."} for k, v in pk5.indicators.items()],
        },
    )
    assert created.status_code == 201, created.text
    response = admin.post(
        "/import/preview", files={"file": ("opop.pdf", SAMPLE, "application/pdf")}
    )
    assert response.status_code == 200, response.text
    item = next(i for i in response.json()["competencies"] if i["code"] == "ПК-5")
    assert item["status"] == "same"
    assert not any(i["changed"] for i in item["indicators"])
