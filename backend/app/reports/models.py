from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Report(Base):
    """Vajra Report Generator (Section 36) - a distinct artifact created
    FROM a validated Investigation ("Finding"), not the investigation
    record itself. Investigation stays about the investigation *process*
    (checklist, confidence, evidence links); Report holds the polished
    narrative meant to leave this machine. One Investigation has at most
    one Report - created on demand, not automatically.
    """

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey("investigations.id"), unique=True, nullable=False)

    summary: Mapped[str] = mapped_column(Text, default="")
    prerequisites: Mapped[str] = mapped_column(Text, default="")
    steps_to_reproduce: Mapped[str] = mapped_column(Text, default="")
    observed_behavior: Mapped[str] = mapped_column(Text, default="")
    expected_behavior: Mapped[str] = mapped_column(Text, default="")
    suggested_remediation: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    investigation = relationship("Investigation", back_populates="report")
