from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.projects.models import HuntMode, ProjectStatus


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    target: str = Field(..., min_length=1, max_length=255, description="Root domain or primary target")
    allowed_domains: list[str] = Field(default_factory=list)
    allowed_subdomains: list[str] = Field(default_factory=list)
    excluded_assets: list[str] = Field(default_factory=list)
    program_rules: str = ""
    testing_restrictions: str = ""
    rate_limit_rps: float = Field(default=1.0, gt=0, le=50)
    mode: HuntMode = HuntMode.GUIDED


class ProjectUpdate(BaseModel):
    name: str | None = None
    allowed_domains: list[str] | None = None
    allowed_subdomains: list[str] | None = None
    excluded_assets: list[str] | None = None
    program_rules: str | None = None
    testing_restrictions: str | None = None
    rate_limit_rps: float | None = Field(default=None, gt=0, le=50)
    mode: HuntMode | None = None
    status: ProjectStatus | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    target: str
    allowed_domains: list[str]
    allowed_subdomains: list[str]
    excluded_assets: list[str]
    program_rules: str
    testing_restrictions: str
    rate_limit_rps: float
    mode: HuntMode
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class ProjectStats(BaseModel):
    assets_discovered: int
    live_hosts: int
    high_priority_assets: int
    recon_jobs_run: int
    last_recon_at: datetime | None = None


class ProjectDetail(ProjectOut):
    stats: ProjectStats
