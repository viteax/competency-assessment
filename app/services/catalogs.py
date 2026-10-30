"""Справочники направления: компетенции, дисциплины и связь ТФ ⇒ компетенции.

Компетенции и дисциплины принадлежат направлению: в разных ОП коды компетенций одни и те же,
а формулировки бывают разные. Дисциплина формирует только компетенции своего направления;
одинаковые коды и названия в разных направлениях – разные записи.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.errors import Conflict, DomainError
from app.services.common import code_key, get_many_or_404, get_or_404, save


def ensure_group_can_move(session: Session, group: models.Group, direction_id: int) -> None:
    """Назначения и попытки ссылаются на вопросы плана, поэтому группа с тестами остаётся в нём."""
    if group.direction_id == direction_id:
        return
    assigned = session.scalar(
        select(models.Assignment.id).where(models.Assignment.group_id == group.id).limit(1)
    )
    if assigned is not None:
        raise Conflict(
            f"группе {group.name} уже назначены тесты: они ссылаются на вопросы её учебного "
            "плана. Перевести такую группу на другой план нельзя"
        )


def competencies_of(session: Session, direction_id: int, ids: list[int]) -> list[models.Competency]:
    """Компетенции по id; все должны относиться к направлению direction_id."""
    competencies = get_many_or_404(session, models.Competency, ids)
    foreign = [c.code for c in competencies if c.direction_id != direction_id]
    if foreign:
        direction = session.get(models.Direction, direction_id)
        raise DomainError(
            f"{', '.join(foreign)} – компетенции другого учебного плана, а нужны компетенции "
            f"плана {direction.label}"
        )
    return competencies


def list_competencies(
    session: Session, direction_id: int | None = None, kind: models.CompetencyKind | None = None
) -> list[models.Competency]:
    stmt = select(models.Competency).options(selectinload(models.Competency.indicators))
    if direction_id is not None:
        stmt = stmt.where(models.Competency.direction_id == direction_id)
    if kind is not None:
        stmt = stmt.where(models.Competency.kind == kind)
    return sorted(session.scalars(stmt), key=lambda c: (c.direction_id, code_key(c.code)))


def _check_code(session: Session, direction_id: int, code: str, own_id: int | None) -> None:
    other = session.scalar(
        select(models.Competency.id).where(
            models.Competency.direction_id == direction_id, models.Competency.code == code
        )
    )
    if other is not None and other != own_id:
        direction = session.get(models.Direction, direction_id)
        raise Conflict(f"в плане {direction.label} уже есть компетенция {code}")


def create_competency(session: Session, data: schemas.CompetencyIn) -> models.Competency:
    get_or_404(session, models.Direction, data.direction_id)
    _check_code(session, data.direction_id, data.code, None)
    return save(
        session,
        models.Competency(
            direction_id=data.direction_id,
            code=data.code,
            kind=data.kind,
            description=data.description,
            indicators=[models.Indicator(**i.model_dump()) for i in data.indicators],
        ),
    )


def update_competency(
    session: Session, competency: models.Competency, data: schemas.CompetencyUpdate
) -> models.Competency:
    _check_code(session, competency.direction_id, data.code, competency.id)
    competency.code = data.code
    competency.kind = data.kind
    competency.description = data.description
    session.commit()
    return competency


def list_disciplines(session: Session, direction_id: int | None = None) -> list[models.Discipline]:
    stmt = (
        select(models.Discipline)
        .order_by(models.Discipline.direction_id, models.Discipline.name)
        .options(selectinload(models.Discipline.competencies))
    )
    if direction_id is not None:
        stmt = stmt.where(models.Discipline.direction_id == direction_id)
    return list(session.scalars(stmt))


def _check_name(session: Session, direction_id: int, name: str, own_id: int | None) -> None:
    other = session.scalar(
        select(models.Discipline.id).where(
            models.Discipline.direction_id == direction_id, models.Discipline.name == name
        )
    )
    if other is not None and other != own_id:
        direction = session.get(models.Direction, direction_id)
        raise Conflict(f"в плане {direction.label} уже есть дисциплина «{name}»")


def save_discipline(
    session: Session, discipline: models.Discipline, data: schemas.DisciplineIn
) -> models.Discipline:
    """Сохраняет дисциплину; направление у новой задано заранее и потом не меняется."""
    _check_name(session, discipline.direction_id, data.name, discipline.id)
    discipline.name = data.name
    discipline.code = data.code or None
    discipline.kind = data.kind
    discipline.competencies = competencies_of(session, discipline.direction_id, data.competency_ids)
    return save(session, discipline)


def create_discipline(session: Session, data: schemas.DisciplineCreate) -> models.Discipline:
    get_or_404(session, models.Direction, data.direction_id)
    return save_discipline(session, models.Discipline(direction_id=data.direction_id), data)


def set_labor_function_competencies(
    session: Session,
    labor_function: models.LaborFunction,
    competency_ids: list[int],
    direction_id: int | None,
) -> None:
    """Связь ТФ ⇒ компетенции. С direction_id меняются только связи этого направления."""
    if direction_id is None:
        labor_function.competencies = get_many_or_404(session, models.Competency, competency_ids)
        return
    get_or_404(session, models.Direction, direction_id)
    others = [c for c in labor_function.competencies if c.direction_id != direction_id]
    labor_function.competencies = others + competencies_of(session, direction_id, competency_ids)
