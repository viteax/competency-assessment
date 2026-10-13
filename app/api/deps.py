from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import models
from app.db import get_session
from app.security import decode_access_token

SessionDep = Annotated[Session, Depends(get_session)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(
    session: SessionDep, token: Annotated[str, Depends(oauth2_scheme)]
) -> models.User:
    user_id = decode_access_token(token)
    user = session.get(models.User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "недействительный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[models.User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> models.User:
    if user.role != models.Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "нужны права администратора")
    return user


def require_student(user: CurrentUser) -> models.Student:
    if user.role != models.Role.STUDENT or user.student is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "доступно только студентам")
    return user.student


AdminUser = Annotated[models.User, Depends(require_admin)]
CurrentStudent = Annotated[models.Student, Depends(require_student)]
