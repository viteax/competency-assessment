from fastapi import APIRouter, Depends

from app import schemas
from app.api.deps import SessionDep, require_admin
from app.services import reports

router = APIRouter(prefix="/reports", tags=["Отчёты"], dependencies=[Depends(require_admin)])


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
def group_competencies(group_id: int, session: SessionDep):
    return reports.group_report(session, group_id)
