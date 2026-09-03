from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.parameters.schemas import ParameterInventoryOut
from app.parameters.service import build_parameter_inventory
from app.projects.models import Project

router = APIRouter(prefix="/api/projects/{project_id}/parameters", tags=["parameter_intelligence"])


@router.get("", response_model=ParameterInventoryOut)
def get_parameter_inventory(project_id: int, db: Session = Depends(get_db)) -> ParameterInventoryOut:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    parameters = build_parameter_inventory(db, project_id)
    return ParameterInventoryOut(parameters=parameters, total_parameters=len(parameters))
