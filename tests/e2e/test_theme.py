import pytest

pytestmark = pytest.mark.e2e


def test_theme_follows_system_and_toggle_persists(new_page):
    page = new_page(color_scheme="dark")
    page.goto("/")

    def background() -> str:
        return page.evaluate("getComputedStyle(document.body).backgroundColor")

    system = background()
    page.click("#theme")
    toggled = background()
    assert toggled != system
    page.reload()
    assert background() == toggled
