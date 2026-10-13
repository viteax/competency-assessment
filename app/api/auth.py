from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app import models, schemas
from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.security import create_access_token, hash_password, verify_password
from app.services.common import get_or_404, save

router = APIRouter(tags=["Пользователи"])


@router.post("/auth/token", response_model=schemas.Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    user = session.scalar(select(models.User).where(models.User.username == form.username))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "неверный логин или пароль")
    return schemas.Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=schemas.UserOut)
def me(user: CurrentUser):
    return user


@router.post("/users", response_model=schemas.UserOut, status_code=201)
def create_user(data: schemas.UserCreate, session: SessionDep, _: AdminUser):
    if data.student_id is not None:
        get_or_404(session, models.Student, data.student_id)
    return save(
        session,
        models.User(
            username=data.username,
            password_hash=hash_password(data.password),
            role=data.role,
            student_id=data.student_id,
        ),
    )


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(session: SessionDep, _: AdminUser):
    return session.scalars(select(models.User).order_by(models.User.username)).all()
