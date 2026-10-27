"""Скрипт выпуска: раздел «Не выпущено» становится разделом версии."""

import datetime

import pytest

from scripts.release import cut_changelog, parse_version, release_notes

CHANGELOG = """# Changelog

## [Не выпущено]

### Исправления
- Починили сортировку.

## [2.0.0] – 2026-10-27

### Возможности
- Старое.
"""


def test_unreleased_becomes_version_section():
    result = cut_changelog(CHANGELOG, "2.0.1", datetime.date(2026, 10, 28))
    assert (
        result
        == """# Changelog

## [Не выпущено]

## [2.0.1] – 2026-10-28

### Исправления
- Починили сортировку.

## [2.0.0] – 2026-10-27

### Возможности
- Старое.
"""
    )


def test_nothing_to_release_and_bad_version():
    empty = CHANGELOG.replace("### Исправления\n- Починили сортировку.\n", "")
    with pytest.raises(ValueError, match="пуст"):
        cut_changelog(empty, "2.0.1", datetime.date(2026, 10, 28))
    with pytest.raises(ValueError, match="1.2.3"):
        parse_version("2.1")
    assert parse_version("2.0.10") > parse_version("2.0.9")


def test_release_notes_are_the_version_section():
    assert release_notes(CHANGELOG, "2.0.0") == "### Возможности\n- Старое.\n"
    cut = cut_changelog(CHANGELOG, "2.0.1", datetime.date(2026, 10, 28))
    assert release_notes(cut, "2.0.1") == "### Исправления\n- Починили сортировку.\n"
    with pytest.raises(ValueError, match="2.0.5"):
        release_notes(CHANGELOG, "2.0.5")
