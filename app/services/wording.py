"""Формулировки компетенций из документов: очистка и сравнение с тем, что уже в базе."""

import re

# Подписи колонок и служебные слова, которые не являются формулировкой.
_NOISE_RE = re.compile(
    r"^(код и наименование.*|наименование.*компетенци.*|индикатор.*достижени.*компетенци.*)$",
    re.IGNORECASE,
)


def clean_wording(text: str) -> str:
    # «социально-\nпсихологические» – перенос по дефису внутри ячейки.
    text = re.sub(r"(?<=[А-Яа-яЁё])-\s*\n\s*(?=[А-Яа-яЁё])", "-", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" .:;,–\u2014-|")
    text = text.removeprefix("– ").removeprefix("\u2014 ")
    if _NOISE_RE.match(text):
        return ""
    # Формулировки в документах пишут то с прописной, то со строчной («способностью к…»).
    return text[:1].upper() + text[1:2000]


def differs(new: str, current: str) -> bool:
    """Отличается ли формулировка по существу: регистр, пробелы и точка в конце не в счет."""

    def norm(text: str) -> str:
        return " ".join(text.split()).strip(" .;").casefold()

    return bool(new) and norm(new) != norm(current)
