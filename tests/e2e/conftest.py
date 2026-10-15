"""Браузерные тесты: настоящий сервер uvicorn + Chromium через Playwright.

Запуск: uv run pytest -m e2e  (в обычный прогон не входят — они медленнее).
Браузер: uv run playwright install chromium, либо путь к своему Chromium в E2E_CHROMIUM.
"""

import os
import re
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SECRET = "e2e-secret-key-that-is-long-enough-1234567"


def _env(db: Path) -> dict[str, str]:
    return {
        **os.environ,
        "ENVIRONMENT": "dev",
        "SECRET_KEY": SECRET,
        "DATABASE_URL": f"sqlite:///{db}",
        "LOG_LEVEL": "WARNING",
    }


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """База с миграциями и демо-данными — готовится один раз, каждому тесту копия."""
    db = tmp_path_factory.mktemp("template") / "seeded.db"
    subprocess.run([sys.executable, "-m", "scripts.seed"], cwd=ROOT, env=_env(db), check=True)
    return db


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(seeded_db: Path, tmp_path: Path) -> Iterator[str]:
    """Свой сервер на чистой копии базы: тесты не влияют друг на друга."""
    db = tmp_path / "app.db"
    shutil.copy(seeded_db, db)
    port = _free_port()
    log = (tmp_path / "server.log").open("w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
        cwd=ROOT,
        env=_env(db),
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if proc.poll() is not None:
                break
            try:
                if httpx.get(f"{url}/ready").status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        else:
            pytest.fail("сервер не запустился")
        if proc.poll() is not None:
            pytest.fail("сервер упал:\n" + (tmp_path / "server.log").read_text())
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        log.close()


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("E2E_CHROMIUM") or None)
        yield b
        b.close()


@pytest.fixture
def new_page(browser: Browser, server: str) -> Iterator[Callable[..., Page]]:
    """Открывает страницы в отдельных контекстах; в конце проверяет, что на страницах не было
    ошибок JavaScript."""
    contexts, errors = [], []

    def _new(**context_args) -> Page:
        ctx = browser.new_context(
            base_url=server, viewport={"width": 1100, "height": 900}, **context_args
        )
        ctx.set_default_timeout(10_000)
        contexts.append(ctx)
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("dialog", lambda d: d.accept())
        return page

    yield _new
    for ctx in contexts:
        ctx.close()
    assert not errors, errors


@pytest.fixture
def page(new_page: Callable[..., Page]) -> Page:
    return new_page()


def login(page: Page, username: str, password: str) -> None:
    page.goto("/")
    page.fill("input[autocomplete=username]", username)
    page.fill("input[type=password]", password)
    page.click("button:text-is('Войти')")


def logout(page: Page) -> None:
    page.click("#who >> text=Выйти")
    page.wait_for_selector("button:text-is('Войти')")


@pytest.fixture
def admin_page(page: Page) -> Page:
    login(page, "admin", "admin123")
    page.wait_for_selector("#who >> text=Выйти")
    return page


def assign_new_test(page: Page, title: str, codes: list[str], per_competency: int = 3) -> None:
    """Вкладка «Назначить тест» администратора: собрать новый тест группе по умолчанию
    (семестр подставляется текущий, вопросы — из завершённых дисциплин)."""
    page.wait_for_selector("text=Завершены до")
    for code in codes:
        page.locator("label", has_text=re.compile(rf"^{code} ")).locator("input").check()
    page.fill("input[placeholder^='любое']", title)
    page.get_by_label("Вопросов на компетенцию").fill(str(per_competency))
    page.click("button:text-is('Собрать и назначить')")
    page.wait_for_selector(".success:has-text('назначен')")
