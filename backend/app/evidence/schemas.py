from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvidenceAttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    investigation_id: int
    filename: str
    content_type: str
    size_bytes: int
    caption: str
    uploaded_at: datetime
    url: str


class MaskedTransactionOut(BaseModel):
    id: int
    identity_profile_name: str | None = None
    method: str
    url: str
    request_headers: dict[str, str]
    request_body: str | None
    status_code: int | None
    response_headers: dict[str, str]
    response_cookies: list[str]
    response_body: str | None
    created_at: datetime
    masking_verifiable: bool


class EvidencePackageOut(BaseModel):
    investigation_id: int
    access_control_snapshot: dict
    transactions: list[MaskedTransactionOut]
    attachments: list[EvidenceAttachmentOut]


class VerifiedBundleFileOut(BaseModel):
    path: str
    size_bytes: int
    compressed_size_bytes: int
    category: str | None = None
    safe_path: bool
    checksum_status: str


class EvidenceBundleVerificationOut(BaseModel):
    filename: str
    valid: bool
    archive_safe: bool
    manifest_valid: bool
    checksums_valid: bool
    compressed_size_bytes: int
    uncompressed_size_bytes: int
    file_count: int
    project: dict | None = None
    investigation: dict | None = None
    masking: dict | None = None
    files: list[VerifiedBundleFileOut]
    warnings: list[str]
    errors: list[str]
