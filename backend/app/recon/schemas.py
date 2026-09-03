from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.recon.models import AssetSource, AssetType, ReconJobStatus, ReconStage


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    hostname: str
    asset_type: AssetType
    source: AssetSource
    discovery_sources: list[str]
    dns_records: dict[str, list[str]]
    resolved_ip: str | None
    is_live: bool | None
    status_code: int | None
    server_header: str | None
    page_title: str | None
    probe_source: str
    technologies: list[str]
    priority_score: int
    priority_reasons: list[str]
    priority_category: str | None
    recommended_action: str | None
    reviewed: bool
    discovered_at: datetime
    last_checked_at: datetime | None


class ReconJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    status: ReconJobStatus
    stage: ReconStage | None
    started_at: datetime
    completed_at: datetime | None
    summary: dict
    notes: list[str]
    error: str | None
    queue_job_id: str | None


class ReconStartResponse(BaseModel):
    job: ReconJobOut
    message: str


class ToolCommandPart(BaseModel):
    token: str
    meaning: str


class ReconTool(BaseModel):
    name: str
    kind: str
    role: str
    status: str
    command: str
    command_parts: list[ToolCommandPart]
    notes: str


class ReconToolStage(BaseModel):
    key: str
    title: str
    active: bool
    what_vajra_does: str
    tools: list[ReconTool]


class ReconToolReference(BaseModel):
    target: str
    rate_limit_rps: float
    note: str
    stages: list[ReconToolStage]
