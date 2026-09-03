from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceAttachment(Base):
    """Screenshot Evidence (Section 32). Scope is deliberately image
    uploads, not arbitrary files or automated capture - this app has no
    headless browser to drive, so "Capture" means the hunter's own
    screenshot, uploaded here and never disconnected from the investigation
    it documents (Section 31's "no evidence should become disconnected
    from the project" is enforced by a hard foreign key, not a convention).
    """

    __tablename__ = "evidence_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey("investigations.id"), nullable=False, index=True)

    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(Integer)
    caption: Mapped[str] = mapped_column(Text, default="")

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    investigation = relationship("Investigation", back_populates="evidence_attachments")
