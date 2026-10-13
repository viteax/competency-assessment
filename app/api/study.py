"""Направления, группы, студенты."""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app import models, schemas
from app.api.deps import SessionDep, require_admin
from app.services.common import get_or_404

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
