from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app import models, schemas
from app.api.cookies import (
    DEVICE_COOKIE,
    clear_session_cookie,
    set_device_cookie,
    set_session_cookie,
)
from app.api.deps import (
    AdminUser,
    CurrentUser,
    SessionDep,
    client_ip,
    get_current_user,
)
from app.errors import Conflict, Unauthorized
from app.security import (
    create_access_token,
    create_device_token,
    device_token_username,
    hash_password,
)
from app.services import auth, registration
from app.services.common import delete_or_conflict, get_or_404, save

router = APIRouter(tags=["Пользователи"])


@router.post("/auth/token", response_model=schemas.Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    response: Response,
    session: SessionDep,
):
    """Вход. Токен возвращается в ответе (для API и Swagger) и ставится в httpOnly-cookie
    (для веб-интерфейса – JavaScript его не видит)."""
    trusted = device_token_username(request.cookies.get(DEVICE_COOKIE)) == form.username
    user = auth.authenticate(session, form.username, form.password, client_ip(request), trusted)
    token = create_access_token(user.id, user.token_version)
    set_session_cookie(response, token)
    set_device_cookie(response, create_device_token(user.username))
    return schemas.Token(access_token=token)


@router.get("/auth/groups", response_model=list[schemas.RegistrationGroup])
def registration_groups(session: SessionDep):
    """Группы для формы регистрации студента (без входа)."""
    return session.scalars(select(models.Group).order_by(models.Group.name)).all()


@router.post("/auth/register", response_model=schemas.Registered, status_code=201)
def register(data: schemas.StudentRegistration, request: Request, session: SessionDep):
    """Студент регистрируется сам: ФИО сверяется со списком группы, пароль свой."""
    user = registration.register_student(
        session, data.group_id, data.full_name, data.password, client_ip(request)
    )
    return schemas.Registered(username=user.username)


@router.post("/auth/logout", status_code=204)
def logout(response: Response):
    clear_session_cookie(response)


@router.get("/auth/session", response_model=schemas.UserOut | None)
def current_session(request: Request, session: SessionDep):
    """Кто вошёл, или null – без 401, чтобы интерфейс мог проверить сессию при загрузке."""
    try:
        return get_current_user(request, session, bearer=None)
    except Unauthorized:
        return None


@router.get("/me", response_model=schemas.UserOut)
def me(user: CurrentUser):
    return user


@router.post("/me/password", status_code=204)
def change_password(data: schemas.PasswordChange, user: CurrentUser, session: SessionDep):
    """Смена своего пароля. Остальные сеансы этого пользователя завершаются."""
    auth.change_password(session, user, data.current_password, data.new_password)


@router.post("/users", response_model=schemas.UserOut, status_code=201)
def create_user(data: schemas.UserCreate, session: SessionDep, _: AdminUser):
    """Создаёт учётку; пароль, заданный администратором, нужно сменить при первом входе."""
    auth.validate_new_password(data.password, data.username)
    if data.student_id is not None:
        get_or_404(session, models.Student, data.student_id)
    return save(
        session,
        models.User(
            username=data.username,
            password_hash=hash_password(data.password),
            role=data.role,
            student_id=data.student_id,
            full_name=data.full_name.strip() if data.full_name else None,
            must_change_password=True,
        ),
    )


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(session: SessionDep, _: AdminUser):
    return session.scalars(select(models.User).order_by(models.User.username)).all()


@router.post("/users/{user_id}/reset-password", response_model=schemas.PasswordReset)
def reset_password(user_id: int, session: SessionDep, _: AdminUser):
    """Новый случайный пароль (показывается один раз); его нужно сменить при входе."""
    user = get_or_404(session, models.User, user_id)
    return schemas.PasswordReset(
        username=user.username, password=auth.reset_password(session, user)
    )


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, session: SessionDep, admin: AdminUser):
    user = get_or_404(session, models.User, user_id)
    if user.id == admin.id:
        raise Conflict("нельзя удалить собственную учётную запись")
    delete_or_conflict(session, user, "на учётную запись есть ссылки")
