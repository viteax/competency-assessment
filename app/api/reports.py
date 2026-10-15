from urllib.parse import quote

from fastapi import APIRouter, Depends, Response

from app import models, schemas
from app.api.deps import SessionDep, require_admin
from app.errors import NotFound
from app.services import report_export, reports
from app.services.common import get_or_404

router = APIRouter(prefix="/reports", tags=["Отчёты"], dependencies=[Depends(require_admin)])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/students/{student_id}/competencies", response_model=schemas.StudentCompetencyReport)
def student_competencies(student_id: int, session: SessionDep):
    return reports.student_report(session, student_id)


@router.get(
    "/students/{student_id}/labor-functions",
    response_model=list[schemas.GeneralLaborFunctionResult],
)
def student_labor_functions(student_id: int, session: SessionDep):
    return reports.labor_function_report(session, student_id)


@router.get("/groups/{group_id}/competencies", response_model=schemas.GroupCompetencyReport)
def group_competencies(group_id: int, session: SessionDep, test_id: int | None = None):
    """Результаты группы по компетенциям: по всем пройденным тестам или по одному."""
    return reports.group_report(session, group_id, test_id)


@router.get("/groups/{group_id}/competencies.xlsx", response_class=Response)
def group_competencies_xlsx(group_id: int, session: SessionDep, test_id: int | None = None):
    """То же в Excel: лист «Компетенции» («N из M» по каждой) и лист «Трудовые функции»."""
    group = get_or_404(session, models.Group, group_id)
    content = report_export.group_results_xlsx(session, group.id, test_id)
    filename = quote(f"Результаты {group.name}.xlsx")
    return Response(
        content,
        media_type=XLSX,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/groups/{group_id}/profile", response_model=schemas.Profile)
def group_profile(
    group_id: int,
    session: SessionDep,
    test_id: int | None = None,
    student_id: int | None = None,
):
    """Данные для «розы ветров» по группе или по одному её студенту."""
    group = get_or_404(session, models.Group, group_id)
    ids = [s.id for s in group.students]
    if student_id is not None:
        if student_id not in ids:
            raise NotFound(f"студента {student_id} нет в группе {group.name}")
        ids = [student_id]
    return reports.profile(session, ids, test_id)
