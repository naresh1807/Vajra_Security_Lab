from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.evidence.service import build_evidence_package
from app.investigations.models import Investigation
from app.projects.models import Project
from app.reports.models import Report
from app.reports.schemas import ReadinessOut, ReportOut, ReportUpdate
from app.reports.service import compute_readiness, seed_report
from app.scopeguard.engine import normalize_target
from app.scopeguard.models import ScopeAuditLog, ScopeDecision

router = APIRouter(prefix="/api/projects/{project_id}/investigations/{inv_id}/report", tags=["reports"])


def _get_investigation_or_404(db: Session, project_id: int, inv_id: int) -> Investigation:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    inv = db.get(Investigation, inv_id)
    if inv is None or inv.project_id != project_id:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv


@router.post("", response_model=ReportOut, status_code=201)
def create_or_get_report(project_id: int, inv_id: int, db: Session = Depends(get_db)) -> Report:
    inv = _get_investigation_or_404(db, project_id, inv_id)
    if inv.report is not None:
        return inv.report

    package = build_evidence_package(db, inv)
    seeded = seed_report(inv, package.transactions)
    report = Report(investigation_id=inv.id, **seeded)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("", response_model=ReportOut)
def get_report(project_id: int, inv_id: int, db: Session = Depends(get_db)) -> Report:
    inv = _get_investigation_or_404(db, project_id, inv_id)
    if inv.report is None:
        raise HTTPException(status_code=404, detail="No report generated yet for this investigation - POST to this URL to create one.")
    return inv.report


@router.patch("", response_model=ReportOut)
def update_report(project_id: int, inv_id: int, payload: ReportUpdate, db: Session = Depends(get_db)) -> Report:
    inv = _get_investigation_or_404(db, project_id, inv_id)
    if inv.report is None:
        raise HTTPException(status_code=404, detail="No report generated yet for this investigation - POST to this URL to create one.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(inv.report, field, value)
    db.commit()
    db.refresh(inv.report)
    return inv.report


@router.get("/readiness", response_model=ReadinessOut)
def get_readiness(project_id: int, inv_id: int, db: Session = Depends(get_db)) -> ReadinessOut:
    inv = _get_investigation_or_404(db, project_id, inv_id)

    scope_verified = False
    if inv.target:
        normalized = normalize_target(inv.target)
        scope_verified = (
            db.query(ScopeAuditLog)
            .filter(
                ScopeAuditLog.project_id == project_id,
                ScopeAuditLog.decision == ScopeDecision.ALLOWED,
                ScopeAuditLog.normalized_target == normalized,
            )
            .first()
            is not None
        )

    return compute_readiness(inv, has_evidence_attachment=bool(inv.evidence_attachments), scope_verified=scope_verified)
