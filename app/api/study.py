"""Направления, группы, студенты."""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app import models, schemas
from app.api.deps import SessionDep, require_admin
from app.services.common import delete_or_conflict, get_or_404

router = APIRouter(tags=["Учебная часть"], dependencies=[Depends(require_admin)])


@router.post("/directions", response_model=schemas.DirectionOut, status_code=201)
def create_direction(data: schemas.DirectionIn, session: SessionDep):
    direction = models.Direction(**data.model_dump())
    session.add(direction)
    session.commit()
    return direction


@router.get("/directions", response_model=list[schemas.DirectionOut])
def list_directions(session: SessionDep):
    return session.scalars(select(models.Direction).order_by(models.Direction.code)).all()


@router.put("/directions/{direction_id}", response_model=schemas.DirectionOut)
def update_direction(direction_id: int, data: schemas.DirectionIn, session: SessionDep):
    direction = get_or_404(session, models.Direction, direction_id)
    direction.code, direction.name = data.code, data.name
    session.commit()
    return direction


@router.delete("/directions/{direction_id}", status_code=204)
def delete_direction(direction_id: int, session: SessionDep):
    direction = get_or_404(session, models.Direction, direction_id)
    delete_or_conflict(session, direction, "у направления есть группы")


@router.post("/groups", response_model=schemas.GroupOut, status_code=201)
def create_group(data: schemas.GroupIn, session: SessionDep):
    get_or_404(session, models.Direction, data.direction_id)
    group = models.Group(**data.model_dump())
    session.add(group)
    session.commit()
    return group


@router.get("/groups", response_model=list[schemas.GroupOut])
def list_groups(session: SessionDep, direction_id: int | None = None):
    stmt = select(models.Group).order_by(models.Group.name)
    if direction_id is not None:
        stmt = stmt.where(models.Group.direction_id == direction_id)
    return session.scalars(stmt).all()


@router.put("/groups/{group_id}", response_model=schemas.GroupOut)
def update_group(group_id: int, data: schemas.GroupIn, session: SessionDep):
    group = get_or_404(session, models.Group, group_id)
    get_or_404(session, models.Direction, data.direction_id)
    group.name, group.direction_id = data.name, data.direction_id
    session.commit()
    return group


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int, session: SessionDep):
    group = get_or_404(session, models.Group, group_id)
    delete_or_conflict(session, group, "в группе есть студенты или назначенные тесты")


@router.post("/students", response_model=schemas.StudentOut, status_code=201)
def create_student(data: schemas.StudentIn, session: SessionDep):
    get_or_404(session, models.Group, data.group_id)
    student = models.Student(**data.model_dump())
    session.add(student)
    session.commit()
    return student


@router.get("/students", response_model=list[schemas.StudentOut])
def list_students(session: SessionDep, group_id: int | None = None):
    stmt = select(models.Student).order_by(models.Student.full_name)
    if group_id is not None:
        stmt = stmt.where(models.Student.group_id == group_id)
    return session.scalars(stmt).all()


@router.get("/students/{student_id}/assignments", response_model=list[schemas.AssignmentOut])
def list_student_assignments(student_id: int, session: SessionDep):
    student = get_or_404(session, models.Student, student_id)
    return session.scalars(
        select(models.Assignment)
        .where(models.Assignment.group_id == student.group_id)
        .order_by(models.Assignment.created_at.desc())
    ).all()
