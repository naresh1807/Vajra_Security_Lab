from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.projects.models import Project
from app.scopeguard.engine import check_scope
from app.scopeguard.models import ScopeAuditLog
from app.scopeguard.schemas import ScopeAuditLogOut, ScopeCheckRequest, ScopeCheckResponse

router = APIRouter(prefix="/api/projects/{project_id}/scopeguard", tags=["scopeguard"])


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/check", response_model=ScopeCheckResponse)
def scope_check(project_id: int, payload: ScopeCheckRequest, db: Session = Depends(get_db)) -> ScopeCheckResponse:
    project = _get_project_or_404(db, project_id)
    result = check_scope(project, payload.target)

    log = ScopeAuditLog(
        project_id=project.id,
        target_input=payload.target,
        normalized_target=result.normalized_target,
        decision=result.decision,
        reason=result.reason,
        operation="manual_check",
    )
    db.add(log)
    db.commit()

    return ScopeCheckResponse(
        target_input=payload.target,
        normalized_target=result.normalized_target,
        decision=result.decision,
        reason=result.reason,
    )


@router.get("/audit-log", response_model=list[ScopeAuditLogOut])
def scope_audit_log(project_id: int, db: Session = Depends(get_db)) -> list[ScopeAuditLog]:
    _get_project_or_404(db, project_id)
    return (
        db.query(ScopeAuditLog)
        .filter(ScopeAuditLog.project_id == project_id)
        .order_by(ScopeAuditLog.created_at.desc())
        .limit(200)
        .all()
    )
