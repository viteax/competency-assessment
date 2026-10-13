"""Демо-учётки из scripts/seed.py. Пароли публичны (README), поэтому в prod они запрещены."""

DEMO_ADMIN = ("admin", "admin123")
DEMO_STUDENT_PASSWORD = "student123"  # логины student1, student2, ...
DEMO_STUDENT_COUNT = 3


def demo_credentials() -> list[tuple[str, str]]:
    students = [(f"student{i}", DEMO_STUDENT_PASSWORD) for i in range(1, DEMO_STUDENT_COUNT + 1)]
    return [DEMO_ADMIN, *students]
