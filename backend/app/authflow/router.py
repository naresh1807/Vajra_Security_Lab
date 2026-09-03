from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.authflow.schemas import AuthFlowOut
from app.authflow.service import build_auth_flow
from app.core.database import get_db
from app.projects.models import Project

router = APIRouter(prefix="/api/projects/{project_id}/auth-flow", tags=["auth_flow"])


@router.get("", response_model=AuthFlowOut)
def get_auth_flow(project_id: int, db: Session = Depends(get_db)) -> AuthFlowOut:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return AuthFlowOut(**build_auth_flow(db, project_id))
