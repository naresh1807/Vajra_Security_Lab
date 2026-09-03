from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


RECON_SOURCE_KEYS = ("subfinder", "wayback", "public_metadata", "katana")


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
    recon_sources: dict[str, bool] | None = None
    playbook: list[dict] | None = None

    @field_validator("recon_sources")
    @classmethod
    def _known_recon_sources(cls, value: dict[str, bool] | None) -> dict[str, bool] | None:
        if value is None:
            return value
        unknown = sorted(set(value) - set(RECON_SOURCE_KEYS))
        if unknown:
            raise ValueError(f"Unknown recon source(s): {', '.join(unknown)}. Valid: {', '.join(RECON_SOURCE_KEYS)}.")
        return value


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
    recon_sources: dict[str, bool] = Field(default_factory=dict)
    playbook: list[dict] = Field(default_factory=list)
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
