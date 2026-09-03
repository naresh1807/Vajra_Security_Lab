from sqlalchemy.orm import Session

from app.projects.models import Project
from app.projects.schemas import ProjectStats
from app.recon.models import Asset, ReconJob, ReconJobStatus
from app.recon.priority import HIGH_PRIORITY_THRESHOLD


def compute_stats(db: Session, project: Project) -> ProjectStats:
    assets = db.query(Asset).filter(Asset.project_id == project.id).all()
    jobs = (
        db.query(ReconJob)
        .filter(ReconJob.project_id == project.id, ReconJob.status == ReconJobStatus.COMPLETED)
        .order_by(ReconJob.completed_at.desc())
        .all()
    )

    return ProjectStats(
        assets_discovered=len(assets),
        live_hosts=sum(1 for a in assets if a.is_live),
        high_priority_assets=sum(1 for a in assets if a.priority_score >= HIGH_PRIORITY_THRESHOLD),
        recon_jobs_run=len(jobs),
        last_recon_at=jobs[0].completed_at if jobs else None,
    )
