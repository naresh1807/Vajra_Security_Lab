"""
Vajra Evidence Vault (Section 31-32).

Screenshot storage is local disk under `settings.upload_dir`, one
subdirectory per investigation so a project reset never orphans files
silently - deleting an investigation deletes its directory too.

`build_evidence_package` is the one place that assembles evidence for
anything leaving the raw HTTP Inspector view (the Report Generator calls
it) - masking happens here, once, rather than being re-implemented at
each call site.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.evidence.masking import is_masking_verifiable, mask_body, mask_cookies, mask_headers
from app.evidence.models import EvidenceAttachment
from app.evidence.schemas import EvidencePackageOut, MaskedTransactionOut
from app.http.models import HttpTransaction
from app.investigations.models import Investigation


def _investigation_dir(project_id: int, investigation_id: int) -> Path:
    path = Path(settings.upload_dir) / str(project_id) / str(investigation_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def attachment_url(attachment_id: int) -> str:
    return f"/api/evidence/{attachment_id}/file"


class UploadValidationError(Exception):
    pass


def save_attachment(
    db: Session, project_id: int, investigation_id: int, filename: str, content_type: str, data: bytes, caption: str
) -> EvidenceAttachment:
    if content_type not in settings.allowed_upload_content_types:
        raise UploadValidationError(
            f"Unsupported file type '{content_type}'. Evidence uploads are screenshots only: "
            f"{', '.join(settings.allowed_upload_content_types)}."
        )
    if len(data) > settings.max_upload_bytes:
        raise UploadValidationError(f"File too large ({len(data)} bytes) - max is {settings.max_upload_bytes} bytes.")

    directory = _investigation_dir(project_id, investigation_id)
    safe_name = f"{uuid.uuid4().hex}_{Path(filename).name}"
    full_path = directory / safe_name
    full_path.write_bytes(data)

    attachment = EvidenceAttachment(
        project_id=project_id,
        investigation_id=investigation_id,
        filename=filename,
        content_type=content_type,
        file_path=str(full_path),
        size_bytes=len(data),
        caption=caption,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def update_attachment(
    db: Session,
    attachment: EvidenceAttachment,
    *,
    caption: str | None = None,
    annotations: list[dict] | None = None,
) -> EvidenceAttachment:
    if caption is not None:
        attachment.caption = caption
    if annotations is not None:
        attachment.annotations = annotations
    db.commit()
    db.refresh(attachment)
    return attachment


def replace_attachment_file(
    db: Session, attachment: EvidenceAttachment, filename: str, content_type: str, data: bytes
) -> EvidenceAttachment:
    """Swap the stored image for a flattened (baked-in) version. The markup
    is now part of the pixels, so the non-destructive annotation list is
    cleared - what you see is what a bundle would contain."""
    if content_type not in settings.allowed_upload_content_types:
        raise UploadValidationError(
            f"Unsupported file type '{content_type}'. Evidence uploads are screenshots only: "
            f"{', '.join(settings.allowed_upload_content_types)}."
        )
    if len(data) > settings.max_upload_bytes:
        raise UploadValidationError(f"File too large ({len(data)} bytes) - max is {settings.max_upload_bytes} bytes.")

    directory = _investigation_dir(attachment.project_id, attachment.investigation_id)
    safe_name = f"{uuid.uuid4().hex}_{Path(filename).name}"
    full_path = directory / safe_name
    full_path.write_bytes(data)

    old_path = attachment.file_path
    attachment.file_path = str(full_path)
    attachment.filename = filename
    attachment.content_type = content_type
    attachment.size_bytes = len(data)
    attachment.annotations = []
    db.commit()
    db.refresh(attachment)
    if old_path and old_path != str(full_path):
        try:
            os.remove(old_path)
        except OSError:
            pass
    return attachment


def delete_attachment(db: Session, attachment: EvidenceAttachment) -> None:
    try:
        os.remove(attachment.file_path)
    except OSError:
        pass  # already gone - don't block deleting the DB record over it
    db.delete(attachment)
    db.commit()


def to_attachment_out(attachment: EvidenceAttachment) -> dict:
    return {
        "id": attachment.id,
        "project_id": attachment.project_id,
        "investigation_id": attachment.investigation_id,
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
        "caption": attachment.caption,
        "annotations": list(attachment.annotations or []),
        "uploaded_at": attachment.uploaded_at,
        "url": attachment_url(attachment.id),
    }


def build_evidence_package(db: Session, investigation: Investigation) -> EvidencePackageOut:
    transactions = (
        db.query(HttpTransaction)
        .filter(
            HttpTransaction.project_id == investigation.project_id,
            HttpTransaction.id.in_(investigation.linked_transaction_ids or [-1]),
        )
        .order_by(HttpTransaction.created_at.asc())
        .all()
    )
    masked_transactions = [
        MaskedTransactionOut(
            id=tx.id,
            identity_profile_name=tx.identity_profile_name,
            method=tx.method,
            url=tx.url,
            request_headers=mask_headers(tx.request_headers),
            request_body=mask_body(tx.request_body),
            status_code=tx.status_code,
            response_headers=mask_headers(tx.response_headers),
            response_cookies=mask_cookies(tx.response_cookies),
            response_body=mask_body(tx.response_body),
            created_at=tx.created_at,
            masking_verifiable=is_masking_verifiable(tx.request_body) and is_masking_verifiable(tx.response_body),
        )
        for tx in transactions
    ]
    return EvidencePackageOut(
        investigation_id=investigation.id,
        access_control_snapshot=investigation.access_control_snapshot or {},
        transactions=masked_transactions,
        attachments=[to_attachment_out(a) for a in investigation.evidence_attachments],
    )
