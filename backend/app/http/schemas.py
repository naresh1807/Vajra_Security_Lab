from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SendRequestPayload(BaseModel):
    method: str = Field(default="GET", pattern="^(?i)(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$")
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    identity_profile_id: int | None = Field(default=None, ge=1)


class HttpTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    identity_profile_id: int | None
    identity_profile_name: str | None
    profile_header_names: list[str]
    method: str
    url: str
    request_headers: dict[str, str]
    request_body: str | None
    status_code: int | None
    response_headers: dict[str, str]
    response_cookies: list[str]
    response_body: str | None
    response_body_truncated: bool
    response_size_bytes: int | None
    timing_ms: float | None
    technologies: list[str]
    interesting_indicators: list[str]
    error: str | None
    created_at: datetime
