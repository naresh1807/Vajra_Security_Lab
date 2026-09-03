from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.projects.models import Project
from app.workbench.schemas import AccessControlWorkbenchOut
from app.workbench.service import build_workbench

router = APIRouter(
    prefix="/api/projects/{project_id}/access-control", tags=["access_control_workbench"]
)


@router.get("/workbench", response_model=AccessControlWorkbenchOut)
def get_workbench(project_id: int, db: Session = Depends(get_db)) -> AccessControlWorkbenchOut:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return AccessControlWorkbenchOut(**build_workbench(db, project_id))
