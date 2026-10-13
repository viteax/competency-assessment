class DomainError(Exception):
    """Ошибка бизнес-логики, которая превращается в HTTP-ответ с понятным сообщением."""

    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409
