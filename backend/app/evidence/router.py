import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.evidence.annotations import AnnotationError, validate_annotations
from app.evidence.models import EvidenceAttachment
from app.evidence.export import EvidenceBundleError, build_evidence_bundle, remove_bundle
from app.evidence.schemas import (
    EvidenceAttachmentOut,
    EvidenceAttachmentUpdate,
    EvidenceBundleVerificationOut,
    EvidencePackageOut,
)
from app.evidence.service import (
    build_evidence_package,
    delete_attachment,
    replace_attachment_file,
    save_attachment,
    to_attachment_out,
    update_attachment,
    UploadValidationError,
)
from app.evidence.verify import EvidenceVerificationLimitError, verify_evidence_bundle
from app.investigations.models import Investigation
from app.projects.models import Project

router = APIRouter(tags=["evidence"])
_ZIP_CONTENT_TYPES = {"application/zip", "application/x-zip-compressed", "application/octet-stream"}


def _get_investigation_or_404(db: Session, project_id: int, inv_id: int) -> Investigation:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    inv = db.get(Investigation, inv_id)
    if inv is None or inv.project_id != project_id:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv


@router.post(
    "/api/projects/{project_id}/investigations/{inv_id}/evidence",
    response_model=EvidenceAttachmentOut,
    status_code=201,
)
async def upload_evidence(
    project_id: int,
    inv_id: int,
    file: UploadFile = File(...),
    caption: str = Form(""),
    db: Session = Depends(get_db),
) -> dict:
    _get_investigation_or_404(db, project_id, inv_id)
    data = await file.read()
    try:
        attachment = save_attachment(
            db, project_id, inv_id, file.filename or "screenshot", file.content_type or "", data, caption
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return to_attachment_out(attachment)


@router.get(
    "/api/projects/{project_id}/investigations/{inv_id}/evidence",
    response_model=list[EvidenceAttachmentOut],
)
def list_evidence(project_id: int, inv_id: int, db: Session = Depends(get_db)) -> list[dict]:
    inv = _get_investigation_or_404(db, project_id, inv_id)
    return [to_attachment_out(a) for a in inv.evidence_attachments]


@router.get(
    "/api/projects/{project_id}/investigations/{inv_id}/evidence/package",
    response_model=EvidencePackageOut,
)
def get_evidence_package(project_id: int, inv_id: int, db: Session = Depends(get_db)) -> EvidencePackageOut:
    inv = _get_investigation_or_404(db, project_id, inv_id)
    return build_evidence_package(db, inv)


@router.post("/api/evidence/verify-bundle", response_model=EvidenceBundleVerificationOut)
async def verify_uploaded_evidence_bundle(file: UploadFile = File(...)) -> EvidenceBundleVerificationOut:
    try:
        if file.content_type not in _ZIP_CONTENT_TYPES:
            raise HTTPException(status_code=422, detail="Evidence verification accepts ZIP files only.")
        return await asyncio.to_thread(
            verify_evidence_bundle,
            file.file,
            file.filename or "uploaded-bundle.zip",
        )
    except EvidenceVerificationLimitError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    finally:
        await file.close()


@router.get("/api/projects/{project_id}/investigations/{inv_id}/evidence/export")
def export_evidence_bundle(project_id: int, inv_id: int, db: Session = Depends(get_db)) -> FileResponse:
    inv = _get_investigation_or_404(db, project_id, inv_id)
    project = db.get(Project, project_id)
    assert project is not None
    try:
        artifact = build_evidence_bundle(db, project, inv)
    except EvidenceBundleError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    return FileResponse(
        artifact.path,
        media_type="application/zip",
        filename=artifact.filename,
        background=BackgroundTask(remove_bundle, artifact.path),
    )


def _attachment_or_404(db: Session, inv_id: int, attachment_id: int) -> EvidenceAttachment:
    attachment = db.get(EvidenceAttachment, attachment_id)
    if attachment is None or attachment.investigation_id != inv_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return attachment


@router.patch(
    "/api/projects/{project_id}/investigations/{inv_id}/evidence/{attachment_id}",
    response_model=EvidenceAttachmentOut,
)
def update_evidence(
    project_id: int,
    inv_id: int,
    attachment_id: int,
    payload: EvidenceAttachmentUpdate,
    db: Session = Depends(get_db),
) -> dict:
    _get_investigation_or_404(db, project_id, inv_id)
    attachment = _attachment_or_404(db, inv_id, attachment_id)
    annotations = None
    if payload.annotations is not None:
        try:
            annotations = validate_annotations(payload.annotations)
        except AnnotationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return to_attachment_out(
        update_attachment(db, attachment, caption=payload.caption, annotations=annotations)
    )


@router.put(
    "/api/projects/{project_id}/investigations/{inv_id}/evidence/{attachment_id}/image",
    response_model=EvidenceAttachmentOut,
)
async def replace_evidence_image(
    project_id: int,
    inv_id: int,
    attachment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """Replace the stored screenshot with a flattened version (markup baked
    into the pixels); clears the non-destructive annotation list."""
    _get_investigation_or_404(db, project_id, inv_id)
    attachment = _attachment_or_404(db, inv_id, attachment_id)
    data = await file.read()
    try:
        updated = replace_attachment_file(
            db, attachment, file.filename or "screenshot.png", file.content_type or "", data
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return to_attachment_out(updated)


@router.delete("/api/projects/{project_id}/investigations/{inv_id}/evidence/{attachment_id}", status_code=204)
def delete_evidence(project_id: int, inv_id: int, attachment_id: int, db: Session = Depends(get_db)) -> None:
    _get_investigation_or_404(db, project_id, inv_id)
    delete_attachment(db, _attachment_or_404(db, inv_id, attachment_id))


@router.get("/api/evidence/{attachment_id}/file")
def get_evidence_file(attachment_id: int, request: Request, db: Session = Depends(get_db)) -> FileResponse:
    attachment = db.get(EvidenceAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    project = db.get(Project, attachment.project_id)
    if project is None or project.owner_id != request.state.user_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(attachment.file_path, media_type=attachment.content_type, filename=attachment.filename)
