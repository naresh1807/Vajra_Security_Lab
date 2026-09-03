from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jobs import QueueUnavailableError, cancel_recon_job, dispatch_recon_job
from app.projects.models import Project
from app.recon.models import Asset, ReconJob, ReconJobStatus
from app.recon.schemas import AssetOut, ReconJobOut, ReconStartResponse, ReconToolReference
from app.recon.tasks import run_recon_job
from app.recon.tool_reference import build_tool_reference

router = APIRouter(prefix="/api/projects/{project_id}", tags=["recon"])


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/recon/start", response_model=ReconStartResponse, status_code=202)
async def start_recon(project_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> ReconStartResponse:
    project = _get_project_or_404(db, project_id)

    running = (
        db.query(ReconJob)
        .filter(ReconJob.project_id == project.id, ReconJob.status.in_([ReconJobStatus.PENDING, ReconJobStatus.RUNNING]))
        .first()
    )
    if running is not None:
        return ReconStartResponse(job=ReconJobOut.model_validate(running), message="A recon job is already in progress.")

    job = ReconJob(project_id=project.id, status=ReconJobStatus.PENDING)
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        job.queue_job_id = dispatch_recon_job(background_tasks, run_recon_job, project.id, job.id)
        db.commit()
        db.refresh(job)
    except QueueUnavailableError as exc:
        job.status = ReconJobStatus.FAILED
        job.error = str(exc)
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ReconStartResponse(
        job=ReconJobOut.model_validate(job),
        message=(
            f"Recon started for {project.target}. Vajra will discover subdomains (passive, via certificate "
            "transparency), check each against ScopeGuard, resolve DNS, probe live hosts, and prioritize results."
        ),
    )


@router.delete("/recon/jobs/{job_id}", response_model=ReconJobOut)
def cancel_job(project_id: int, job_id: int, db: Session = Depends(get_db)) -> ReconJob:
    _get_project_or_404(db, project_id)
    job = db.get(ReconJob, job_id)
    if job is None or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="Recon job not found")
    if job.status != ReconJobStatus.PENDING:
        raise HTTPException(status_code=409, detail="Only queued jobs that have not started can be cancelled safely.")
    try:
        if not cancel_recon_job(job.queue_job_id):
            raise HTTPException(status_code=409, detail="This queue backend cannot cancel an in-process job.")
    except QueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    job.status = ReconJobStatus.BLOCKED
    job.error = "Cancelled by user before completion."
    db.commit(); db.refresh(job)
    return job


@router.get("/recon/jobs", response_model=list[ReconJobOut])
def list_recon_jobs(project_id: int, db: Session = Depends(get_db)) -> list[ReconJob]:
    _get_project_or_404(db, project_id)
    return db.query(ReconJob).filter(ReconJob.project_id == project_id).order_by(ReconJob.started_at.desc()).all()


@router.get("/recon/tool-reference", response_model=ReconToolReference)
def recon_tool_reference(project_id: int, db: Session = Depends(get_db)) -> ReconToolReference:
    project = _get_project_or_404(db, project_id)
    return ReconToolReference(**build_tool_reference(project))


@router.get("/assets", response_model=list[AssetOut])
def list_assets(project_id: int, db: Session = Depends(get_db)) -> list[Asset]:
    _get_project_or_404(db, project_id)
    return (
        db.query(Asset)
        .filter(Asset.project_id == project_id)
        .order_by(Asset.priority_score.desc(), Asset.hostname.asc())
        .all()
    )


@router.patch("/assets/{asset_id}/reviewed", response_model=AssetOut)
def mark_asset_reviewed(project_id: int, asset_id: int, db: Session = Depends(get_db)) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.project_id != project_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.reviewed = not asset.reviewed
    db.commit()
    db.refresh(asset)
    return asset
