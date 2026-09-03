from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.projects.models import Project
from app.projects.playbook import PlaybookError, default_playbook, validate_playbook
from app.projects.schemas import ProjectCreate, ProjectDetail, ProjectOut, ProjectUpdate
from app.projects.service import compute_stats

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, request: Request, db: Session = Depends(get_db)) -> Project:
    project = Project(owner_id=request.state.user_id, playbook=default_playbook(), **payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(request: Request, db: Session = Depends(get_db)) -> list[Project]:
    return db.query(Project).filter(Project.owner_id == request.state.user_id).order_by(Project.created_at.desc()).all()


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectDetail:
    project = _get_project_or_404(db, project_id)
    stats = compute_stats(db, project)
    return ProjectDetail(**ProjectOut.model_validate(project).model_dump(), stats=stats)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)) -> Project:
    project = _get_project_or_404(db, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "playbook":
            try:
                value = validate_playbook(value)
            except PlaybookError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)) -> None:
    project = _get_project_or_404(db, project_id)
    db.delete(project)
    db.commit()
