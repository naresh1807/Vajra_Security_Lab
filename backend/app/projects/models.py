import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HuntMode(str, enum.Enum):
    GUIDED = "guided"
    STANDARD = "standard"
    ADVANCED = "advanced"


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Project(Base):
    """A bug bounty program the hunter is authorized to test.

    The scope fields here (allowed_domains, allowed_subdomains,
    excluded_assets, program_rules, rate_limit_rps, testing_restrictions)
    are the single source of truth ScopeGuard checks every target against.
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)

    allowed_domains: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_subdomains: Mapped[list[str]] = mapped_column(JSON, default=list)
    excluded_assets: Mapped[list[str]] = mapped_column(JSON, default=list)
    program_rules: Mapped[str] = mapped_column(Text, default="")
    testing_restrictions: Mapped[str] = mapped_column(Text, default="")
    rate_limit_rps: Mapped[float] = mapped_column(Float, default=1.0)

    mode: Mapped[HuntMode] = mapped_column(Enum(HuntMode), default=HuntMode.GUIDED)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.ACTIVE)

    # Per-project recon pipeline switches (Section 42: "User changes recon
    # pipeline"). {source_key: bool}. A False disables that optional source
    # for this project even when the deployment enables it; a True never
    # overrides a deployment that has turned the source off. crt.sh and the
    # DNS fallback are always on. See recon/service.py `_recon_source_enabled`.
    recon_sources: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    owner = relationship("User", back_populates="projects")

    assets = relationship("Asset", back_populates="project", cascade="all, delete-orphan")
    recon_jobs = relationship("ReconJob", back_populates="project", cascade="all, delete-orphan")
    audit_logs = relationship("ScopeAuditLog", back_populates="project", cascade="all, delete-orphan")
    http_transactions = relationship("HttpTransaction", back_populates="project", cascade="all, delete-orphan")
    identity_profiles = relationship("IdentityProfile", back_populates="project", cascade="all, delete-orphan")
    access_control_scenarios = relationship(
        "AccessControlScenario", back_populates="project", cascade="all, delete-orphan"
    )
    investigations = relationship("Investigation", back_populates="project", cascade="all, delete-orphan")
    js_files = relationship("JsFile", back_populates="project", cascade="all, delete-orphan")
    discovered_endpoints = relationship("DiscoveredEndpoint", back_populates="project", cascade="all, delete-orphan")
    crawl_rejections = relationship("CrawlRejection", back_populates="project", cascade="all, delete-orphan")
    public_metadata_documents = relationship(
        "PublicMetadataDocument", back_populates="project", cascade="all, delete-orphan"
    )
