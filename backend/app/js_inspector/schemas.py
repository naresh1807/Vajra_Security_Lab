from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.js_inspector.models import FindingType


class AnalyzeJsPayload(BaseModel):
    url: str


class JsFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    finding_type: FindingType
    value: str
    context: str | None
    metadata_: dict = {}


class JsFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    url: str
    status_code: int | None
    size_bytes: int | None
    error: str | None
    fetched_at: datetime
    findings: list[JsFindingOut]
