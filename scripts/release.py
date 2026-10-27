"""Готовит выпуск версии: номер в pyproject.toml и uv.lock, раздел «Не выпущено» в CHANGELOG.md
становится разделом новой версии с сегодняшней датой.

    uv run python -m scripts.release 2.0.1

Дальше – коммит, пуш и тег v2.0.1 (docs/deploy.md, раздел «Выпуск версии»).
"""

import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNRELEASED = "## [Не выпущено]\n"


def parse_version(text: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"\d+\.\d+\.\d+", text):
        raise ValueError(f"версия должна быть вида 1.2.3, получено: {text!r}")
    major, minor, patch = (int(part) for part in text.split("."))
    return major, minor, patch


def cut_changelog(changelog: str, version: str, date: datetime.date) -> str:
    """Записи из «Не выпущено» переходят в раздел версии, «Не выпущено» остается пустым."""
    if changelog.count(UNRELEASED) != 1:
        raise ValueError("в CHANGELOG.md нет раздела «## [Не выпущено]»")
    head, rest = changelog.split(UNRELEASED)
    entries, sep, older = rest.partition("\n## [")
    if not entries.strip():
        raise ValueError("раздел «Не выпущено» пуст – выпускать нечего")
    section = f"## [{version}] – {date.isoformat()}\n{entries.rstrip()}\n"
    return f"{head}{UNRELEASED}\n{section}{sep}{older}"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    version = sys.argv[1].removeprefix("v")
    try:
        new = parse_version(version)
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        current = re.search(r'^version = "(.+)"$', pyproject, re.MULTILINE).group(1)
        if new <= parse_version(current):
            raise ValueError(f"версия {version} не новее текущей {current}")
        changelog = cut_changelog(
            (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), version, datetime.date.today()
        )
    except ValueError as exc:
        sys.exit(f"ошибка: {exc}")

    (ROOT / "pyproject.toml").write_text(
        pyproject.replace(f'version = "{current}"', f'version = "{version}"', 1), encoding="utf-8"
    )
    (ROOT / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    subprocess.run(["uv", "lock", "--quiet"], cwd=ROOT, check=True)  # версия проекта в uv.lock
    print(f"Готово: {current} → {version}. Проверьте CHANGELOG.md, затем:")
    print(f'  git commit -am "Release {version}" && git push')
    print(f"  и тег v{version} – GitHub → Releases → Draft a new release (docs/deploy.md)")


if __name__ == "__main__":
    main()
