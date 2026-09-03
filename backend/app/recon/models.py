import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AssetType(str, enum.Enum):
    SUBDOMAIN = "subdomain"
    HOST = "host"
    URL = "url"
    API = "api"
    JAVASCRIPT = "javascript"


class AssetSource(str, enum.Enum):
    CRTSH = "crtsh"
    DNS = "dns"
    MANUAL = "manual"


class ReconJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class ReconStage(str, enum.Enum):
    SUBDOMAIN_DISCOVERY = "subdomain_discovery"
    DNS_RESOLUTION = "dns_resolution"
    LIVE_HOST_PROBING = "live_host_probing"
    TECHNOLOGY_DETECTION = "technology_detection"
    PRIORITIZATION = "prioritization"
    DONE = "done"


class Asset(Base):
    """A single discovered attack-surface asset (Vajra Surface, Section 10)."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)

    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    asset_type: Mapped[AssetType] = mapped_column(Enum(AssetType), default=AssetType.SUBDOMAIN)
    source: Mapped[AssetSource] = mapped_column(Enum(AssetSource), default=AssetSource.CRTSH)
    discovery_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    dns_records: Mapped[dict] = mapped_column(JSON, default=dict)

    resolved_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_live: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    server_header: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    probe_source: Mapped[str] = mapped_column(String(50), default="vajra-httpx")
    technologies: Mapped[list[str]] = mapped_column(JSON, default=list)

    priority_score: Mapped[int] = mapped_column(Integer, default=0)
    priority_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    priority_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)

    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="assets")


class ReconJob(Base):
    __tablename__ = "recon_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)

    status: Mapped[ReconJobStatus] = mapped_column(Enum(ReconJobStatus), default=ReconJobStatus.PENDING)
    stage: Mapped[ReconStage | None] = mapped_column(Enum(ReconStage), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    queue_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    project = relationship("Project", back_populates="recon_jobs")
