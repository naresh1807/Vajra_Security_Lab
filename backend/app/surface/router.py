from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.projects.models import Project
from app.surface.models import CrawlRejection, DiscoveredEndpoint, PublicMetadataDocument
from app.surface.schemas import CrawlRejectionOut, DiscoveredEndpointOut, PublicMetadataDocumentOut

router = APIRouter(prefix="/api/projects/{project_id}/surface", tags=["attack_surface"])


def _project(db: Session, project_id: int) -> None:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/endpoints", response_model=list[DiscoveredEndpointOut])
def list_endpoints(project_id: int, db: Session = Depends(get_db)) -> list[DiscoveredEndpoint]:
    _project(db, project_id)
    return db.query(DiscoveredEndpoint).filter(DiscoveredEndpoint.project_id == project_id).order_by(
        DiscoveredEndpoint.hostname, DiscoveredEndpoint.path
    ).all()


@router.get("/endpoints/{endpoint_id}", response_model=DiscoveredEndpointOut)
def get_endpoint(project_id: int, endpoint_id: int, db: Session = Depends(get_db)) -> DiscoveredEndpoint:
    _project(db, project_id)
    endpoint = db.get(DiscoveredEndpoint, endpoint_id)
    if endpoint is None or endpoint.project_id != project_id:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return endpoint


@router.get("/rejections", response_model=list[CrawlRejectionOut])
def list_rejections(project_id: int, db: Session = Depends(get_db)) -> list[CrawlRejection]:
    _project(db, project_id)
    return db.query(CrawlRejection).filter(CrawlRejection.project_id == project_id).order_by(
        CrawlRejection.created_at.desc()
    ).limit(200).all()


@router.get("/metadata", response_model=list[PublicMetadataDocumentOut])
def list_metadata(project_id: int, db: Session = Depends(get_db)) -> list[PublicMetadataDocument]:
    _project(db, project_id)
    return db.query(PublicMetadataDocument).filter(PublicMetadataDocument.project_id == project_id).order_by(
        PublicMetadataDocument.fetched_at.desc(), PublicMetadataDocument.url
    ).all()
