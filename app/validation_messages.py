"""Сообщения об ошибках проверки запроса (422) по-русски.

FastAPI отдаёт ошибки pydantic по-английски («Field required», «String should have at least
1 character»), а интерфейс показывает их пользователю как есть. Здесь они переводятся в одном
месте; формат ответа (список с loc, type, msg) сохраняется для клиентов API. Введённое
значение (input) в ответ не попадает: там может оказаться пароль.
"""

from typing import Any

# Названия полей, которые видит пользователь.
FIELDS = {
    "answers": "Ответы",
    "assignment_id": "Назначение",
    "code": "Код",
    "competency_id": "Компетенция",
    "competency_ids": "Компетенции",
    "current_password": "Текущий пароль",
    "description": "Формулировка",
    "difficulty": "Уровень сложности",
    "direction_id": "Направление",
    "discipline_id": "Дисциплина",
    "discipline_ids": "Дисциплины",
    "email": "E-mail",
    "first_semester": "Первый семестр",
    "full_name": "ФИО",
    "group_id": "Группа",
    "image": "Картинка",
    "kind": "Тип задания",
    "last_semester": "Последний семестр",
    "legend": "Подпись",
    "mastery_threshold": "Порог",
    "name": "Название",
    "new_password": "Новый пароль",
    "options": "Варианты",
    "password": "Пароль",
    "qualification_level": "Уровень квалификации",
    "questions": "Число вопросов",
    "questions_per_competency": "Вопросов на компетенцию",
    "quotas": "Квоты",
    "role": "Роль",
    "semester": "Семестр",
    "start_year": "Год набора",
    "teacher_id": "Преподаватель",
    "test_id": "Тест",
    "text": "Текст",
    "title": "Название",
    "username": "Логин",
    "variant_count": "Число вариантов",
}


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _message(error: dict[str, Any]) -> str:
    kind, ctx = error["type"], error.get("ctx") or {}
    match kind:
        case "missing":
            return "обязательное поле"
        case "string_too_short":
            n = ctx["min_length"]
            return (
                "не заполнено"
                if n == 1
                else f"не короче {n} {_plural(n, 'символа', 'символов', 'символов')}"
            )
        case "string_too_long":
            n = ctx["max_length"]
            return f"не длиннее {n} {_plural(n, 'символа', 'символов', 'символов')}"
        case "too_short":
            n = ctx["min_length"]
            return "нужен хотя бы один элемент" if n == 1 else f"нужно не меньше {n} элементов"
        case "too_long":
            return f"не больше {ctx['max_length']} элементов"
        case "greater_than_equal":
            return f"не меньше {ctx['ge']}"
        case "greater_than":
            return f"больше {ctx['gt']}"
        case "less_than_equal":
            return f"не больше {ctx['le']}"
        case "less_than":
            return f"меньше {ctx['lt']}"
        case "int_parsing" | "int_type" | "int_from_float":
            return "нужно целое число"
        case "float_parsing" | "float_type":
            return "нужно число"
        case "bool_parsing" | "bool_type":
            return "нужно «да» или «нет»"
        case "string_type":
            return "нужен текст"
        case "list_type":
            return "нужен список"
        case "dict_type" | "model_type" | "model_attributes_type":
            return "неверный формат данных"
        case "enum" | "literal_error":
            return f"допустимые значения: {ctx.get('expected', '').replace(' or ', ', ')}"
        case "string_pattern_mismatch":
            return "неверный формат"
        case "extra_forbidden":
            return "неизвестное поле"
        case "json_invalid":
            return "некорректный JSON"
        case "value_error" | "assertion_error":
            # Сообщения наших проверок уже по-русски, pydantic добавляет «Value error, ».
            return (
                str(error["msg"]).removeprefix("Value error, ").removeprefix("Assertion failed, ")
            )
    return str(error["msg"])


def _field(loc: tuple) -> str | None:
    """Последний именованный элемент пути: ("body", "options", 0, "text") → «Текст»."""
    names = [p for p in loc if isinstance(p, str) and p not in ("body", "query", "path", "form")]
    return FIELDS.get(names[-1], names[-1]) if names else None


def translate(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for error in errors:
        message = _message(error)
        field = _field(tuple(error.get("loc", ())))
        # У проверок всей модели (model_validator) поля нет – сообщение уже самодостаточно.
        if field and error["type"] not in ("value_error", "assertion_error"):
            message = f"{field}: {message}"
        result.append({"loc": list(error.get("loc", ())), "type": error["type"], "msg": message})
    return result
