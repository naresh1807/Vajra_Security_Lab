from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DiscoveredEndpointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    url: str
    normalized_url: str
    hostname: str
    path: str
    method: str
    query_parameters: list[str]
    parameter_details: list[dict]
    request_body_content_types: list[str]
    security_requirements: list[dict]
    tags: list[str]
    operation_id: str | None
    summary: str | None
    deprecated: bool
    request_template: dict
    source: str
    status_code: int | None
    content_type: str | None
    first_seen_at: datetime
    last_seen_at: datetime


class CrawlRejectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    reason: str
    source: str
    created_at: datetime


class PublicMetadataDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    url: str
    kind: str
    status_code: int | None
    content_type: str | None
    content_sha256: str | None
    entries: list[dict[str, str]]
    error: str | None
    fetched_at: datetime
