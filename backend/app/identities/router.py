from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.identities.models import IdentityProfile
from app.identities.schemas import IdentityProfileCreate, IdentityProfileOut, IdentityProfileUpdate
from app.identities.service import MAX_PROFILES_PER_PROJECT, get_profile_or_404, profile_out, validate_secret_headers
from app.projects.models import Project

router = APIRouter(prefix="/api/projects/{project_id}/identities", tags=["identities"])


def _project(db: Session, project_id: int) -> None:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Identity name cannot be blank.")
    return cleaned


@router.get("", response_model=list[IdentityProfileOut])
def list_profiles(project_id: int, db: Session = Depends(get_db)) -> list[IdentityProfileOut]:
    _project(db, project_id)
    profiles = db.query(IdentityProfile).filter(IdentityProfile.project_id == project_id).order_by(
        IdentityProfile.name
    ).all()
    return [profile_out(profile) for profile in profiles]


@router.post("", response_model=IdentityProfileOut, status_code=201)
def create_profile(
    project_id: int,
    payload: IdentityProfileCreate,
    db: Session = Depends(get_db),
) -> IdentityProfileOut:
    _project(db, project_id)
    if db.query(IdentityProfile).filter(IdentityProfile.project_id == project_id).count() >= MAX_PROFILES_PER_PROJECT:
        raise HTTPException(status_code=409, detail=f"A project can contain at most {MAX_PROFILES_PER_PROJECT} identities.")
    profile = IdentityProfile(
        project_id=project_id,
        name=_clean_name(payload.name),
        description=payload.description.strip(),
        secret_headers=validate_secret_headers(payload.headers),
    )
    db.add(profile)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An identity with this name already exists in the project.") from exc
    db.refresh(profile)
    return profile_out(profile)


@router.patch("/{profile_id}", response_model=IdentityProfileOut)
def update_profile(
    project_id: int,
    profile_id: int,
    payload: IdentityProfileUpdate,
    db: Session = Depends(get_db),
) -> IdentityProfileOut:
    _project(db, project_id)
    profile = get_profile_or_404(db, project_id, profile_id)
    if payload.name is not None:
        profile.name = _clean_name(payload.name)
    if payload.description is not None:
        profile.description = payload.description.strip()
    if payload.headers is not None:
        profile.secret_headers = validate_secret_headers(payload.headers)
    if payload.enabled is not None:
        profile.enabled = payload.enabled
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An identity with this name already exists in the project.") from exc
    db.refresh(profile)
    return profile_out(profile)


@router.delete("/{profile_id}", status_code=204)
def delete_profile(project_id: int, profile_id: int, db: Session = Depends(get_db)) -> Response:
    _project(db, project_id)
    profile = get_profile_or_404(db, project_id, profile_id)
    db.delete(profile)
    db.commit()
    return Response(status_code=204)
