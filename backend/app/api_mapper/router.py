from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api_mapper.schemas import ApiMapOut
from app.api_mapper.service import build_api_map
from app.core.database import get_db
from app.projects.models import Project

router = APIRouter(prefix="/api/projects/{project_id}/api-map", tags=["api_mapper"])


@router.get("", response_model=ApiMapOut)
def get_api_map(project_id: int, db: Session = Depends(get_db)) -> ApiMapOut:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    grouped = build_api_map(db, project_id)
    total = sum(len(v) for v in grouped.values())
    return ApiMapOut(categories=grouped, total_endpoints=total)
