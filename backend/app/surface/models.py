from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiscoveredEndpoint(Base):
    __tablename__ = "discovered_endpoints"
    __table_args__ = (
        UniqueConstraint("project_id", "normalized_url", "method", name="uq_endpoint_project_url_method"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(1500), nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="GET")
    query_parameters: Mapped[list[str]] = mapped_column(JSON, default=list)
    parameter_details: Mapped[list[dict]] = mapped_column(JSON, default=list)
    request_body_content_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    security_requirements: Mapped[list[dict]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    operation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    request_template: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(50), default="katana")
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project = relationship("Project", back_populates="discovered_endpoints")


class CrawlRejection(Base):
    __tablename__ = "crawl_rejections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="katana")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project = relationship("Project", back_populates="crawl_rejections")


class PublicMetadataDocument(Base):
    __tablename__ = "public_metadata_documents"
    __table_args__ = (UniqueConstraint("project_id", "url", name="uq_metadata_project_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entries: Mapped[list[dict]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project = relationship("Project", back_populates="public_metadata_documents")
