import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FindingType(str, enum.Enum):
    API_ROUTE = "api_route"
    GRAPHQL_URL = "graphql_url"
    WEBSOCKET_URL = "websocket_url"
    CONFIG_REFERENCE = "config_reference"
    SOURCE_MAP = "source_map"
    POTENTIAL_SECRET = "potential_secret"


class JsFile(Base):
    """A JavaScript file Vajra fetched and analyzed (Section 19)."""

    __tablename__ = "js_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)

    url: Mapped[str] = mapped_column(String(2000))
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project = relationship("Project", back_populates="js_files")
    findings = relationship("JsFinding", back_populates="js_file", cascade="all, delete-orphan")


class JsFinding(Base):
    """A single thing extracted from a JsFile: a route, a URL, a masked secret, ..."""

    __tablename__ = "js_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    js_file_id: Mapped[int] = mapped_column(ForeignKey("js_files.id"), nullable=False, index=True)

    finding_type: Mapped[FindingType] = mapped_column(Enum(FindingType))
    value: Mapped[str] = mapped_column(String(2000))
    context: Mapped[str | None] = mapped_column(String(300), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    js_file = relationship("JsFile", back_populates="findings")
