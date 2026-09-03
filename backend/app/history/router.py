from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.history.schemas import HuntHistoryOut
from app.history.service import build_hunt_history
from app.projects.models import Project

router = APIRouter(prefix="/api/projects/{project_id}/history", tags=["history"])


@router.get("", response_model=HuntHistoryOut)
def get_hunt_history(project_id: int, category: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)) -> HuntHistoryOut:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return build_hunt_history(db, project_id, category, limit, offset)
