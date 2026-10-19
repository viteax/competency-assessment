"""Кабинет преподавателя: закреплённые дисциплины, что и сколько разработать, выгрузка ФОМ."""

from fastapi import APIRouter, Response

from app import schemas
from app.api.deps import SessionDep, TeacherUser
from app.api.files import DOCX, attachment
from app.services import fund, teaching

router = APIRouter(prefix="/teacher", tags=["Преподаватель"])


@router.get("/disciplines", response_model=list[schemas.TeacherDiscipline])
def my_disciplines(teacher: TeacherUser, session: SessionDep):
    """Дисциплины, закреплённые за преподавателем, с квотами и прогрессом по компетенциям."""
    return teaching.progress(session, teacher)


@router.get("/disciplines/{discipline_id}/fund.docx", response_class=Response)
def my_fund(discipline_id: int, teacher: TeacherUser, session: SessionDep, key: bool = False):
    """ФОМ своей дисциплины в Word для учебного управления: без ответов или с ответами."""
    teaching.own_discipline(session, teacher, discipline_id)
    content, filename = fund.discipline_document(session, discipline_id, key)
    return attachment(content, filename, DOCX)
