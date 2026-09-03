from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.identities.models import IdentityProfile
from app.identities.schemas import IdentityProfileOut

_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_BLOCKED_HEADERS = {
    "host", "content-length", "transfer-encoding", "connection", "proxy-authorization",
    "proxy-connection", "upgrade", "expect", "te", "trailer",
}
MAX_TOTAL_HEADER_CHARS = 32_768
MAX_PROFILES_PER_PROJECT = 20


def validate_secret_headers(headers: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    seen: set[str] = set()
    total = 0
    for raw_name, raw_value in headers.items():
        name, value = raw_name.strip(), raw_value.strip()
        lower = name.lower()
        if not name or not _HEADER_NAME.fullmatch(name):
            raise HTTPException(status_code=422, detail=f"Invalid identity header name: {raw_name!r}")
        if lower in _BLOCKED_HEADERS or lower.startswith(("proxy-", "sec-")):
            raise HTTPException(status_code=422, detail=f"Identity profiles cannot control the '{name}' header.")
        if lower in seen:
            raise HTTPException(status_code=422, detail=f"Duplicate identity header name: {name}")
        if not value or "\r" in value or "\n" in value or len(value) > 8192:
            raise HTTPException(status_code=422, detail=f"Identity header '{name}' has an invalid value.")
        seen.add(lower)
        total += len(name) + len(value)
        normalized[name] = value
    if not normalized:
        raise HTTPException(status_code=422, detail="At least one identity header is required.")
    if total > MAX_TOTAL_HEADER_CHARS:
        raise HTTPException(status_code=422, detail="Identity headers exceed the 32 KiB storage limit.")
    return normalized


def profile_out(profile: IdentityProfile) -> IdentityProfileOut:
    return IdentityProfileOut(
        id=profile.id,
        project_id=profile.project_id,
        name=profile.name,
        description=profile.description,
        header_names=sorted(profile.secret_headers, key=str.lower),
        enabled=profile.enabled,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def get_profile_or_404(db: Session, project_id: int, profile_id: int) -> IdentityProfile:
    profile = db.get(IdentityProfile, profile_id)
    if profile is None or profile.project_id != project_id:
        raise HTTPException(status_code=404, detail="Identity profile not found")
    return profile


def merge_profile_headers(manual: dict[str, str], profile_headers: dict[str, str]) -> dict[str, str]:
    """Merge case-insensitively, with the explicitly selected profile winning."""
    profile_names = {name.lower() for name in profile_headers}
    return {
        **{name: value for name, value in manual.items() if name.lower() not in profile_names},
        **profile_headers,
    }
