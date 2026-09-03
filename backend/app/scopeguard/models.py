import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScopeDecision(str, enum.Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    MANUAL_REVIEW = "manual_review"


class ScopeAuditLog(Base):
    """Every target that ever passed through ScopeGuard (Section 5, 46).

    No recon or HTTP operation runs against a target without a row here.
    This is the audit trail referenced by Section 38 (Hunt History).
    """

    __tablename__ = "scope_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)

    target_input: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_target: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[ScopeDecision] = mapped_column(Enum(ScopeDecision), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    operation: Mapped[str] = mapped_column(String(100), default="manual_check")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project = relationship("Project", back_populates="audit_logs")
