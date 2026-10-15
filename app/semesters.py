"""Номер семестра по году набора и дате.

Учебный год начинается 1 сентября: сентябрь–январь — нечётный семестр, февраль–август — чётный
(летом действует только что закончившийся чётный: его дисциплины уже завершены).
"""

from datetime import date


def current_semester(start_year: int, today: date | None = None) -> int:
    today = today or date.today()
    # Сколько полных учебных лет прошло к началу текущего учебного года.
    academic_year = today.year if today.month >= 9 else today.year - 1
    years = academic_year - start_year
    in_autumn = today.month >= 9 or today.month == 1
    return max(1, 2 * years + (1 if in_autumn else 2))
