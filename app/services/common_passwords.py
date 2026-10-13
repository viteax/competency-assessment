"""Самые распространённые пароли — их перебирают первыми. Список короткий и намеренно
включает «русские» варианты: раскладку йцукен, транслит, даты и номера групп."""

_COMMON = frozenset(
    """
    12345678 123456789 1234567890 0987654321 87654321 11111111 00000000 12341234 11223344
    12121212 88888888 77777777 55555555 66666666 99999999 22222222 33333333 44444444
    123123123 147258369 159753456 789456123 12344321 13579246 1q2w3e4r 1q2w3e4r5t
    1qaz2wsx qwerty12 qwerty123 qwertyui qwertyuiop asdfghjk asdfghjkl zxcvbnm123
    password password1 password123 passw0rd p@ssw0rd iloveyou princess sunshine
    football baseball monkey123 dragon123 superman batman123 welcome1 letmein1
    admin123 administrator student student123 student1 qwerty1234 abc12345 abcd1234
    йцукенгш йцукенгшщз фывапролд пароль123 пароль12 parol123 privet123 privetik
    lyubov123 lubov123 nastya123 natasha1 maxim123 dmitriy1 sergey123 andrey123
    alexander tusur123 tusur2024 tusur2025 tusur2026 tomsk123 tomsk2024 tomsk2025
    qazwsxedc zaq12wsx 1234qwer qwer1234 q1w2e3r4 q1w2e3r4t5 a1b2c3d4 aaaaaaaa
    """.split()
)


def is_common_password(password: str) -> bool:
    lowered = password.casefold()
    if lowered in _COMMON:
        return True
    if len(set(lowered)) <= 2:  # aaaaaaaa, abababab
        return True
    # Только цифры — дата рождения или телефон, такие перебираются за секунды.
    return lowered.isdigit() and len(lowered) < 12
