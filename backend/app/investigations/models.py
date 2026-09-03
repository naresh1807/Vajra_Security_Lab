import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InvestigationStatus(str, enum.Enum):
    OPEN = "open"
    FALSE_POSITIVE = "false_positive"
    VALIDATED = "validated"
    CLOSED = "closed"


class InvestigationSource(str, enum.Enum):
    ASSET = "asset"
    ANALYZER_FINDING = "analyzer_finding"
    DIFF_RESULT = "diff_result"
    MANUAL = "manual"


# The exact six questions from Section 34 ("False Positive Engine"). Fixed
# keys so the frontend can render a stable checklist and the backend can
# compute a hint from it - see investigations/service.py.
FALSE_POSITIVE_QUESTIONS: dict[str, str] = {
    "authentication_required": "Was authentication required?",
    "data_actually_sensitive": "Is the data actually sensitive?",
    "object_belongs_to_other_account": "Does the object belong to another controlled account?",
    "behavior_intended": "Is the behavior intended (per program design)?",
    "program_excludes_issue": "Does the program explicitly exclude this issue?",
    "reproducible": "Can the behavior be reproduced?",
}


class Investigation(Base):
    """Vajra Investigation Workspace (Section 24) / Findings (Section 33).

    A single table covers the SIGNAL -> CANDIDATE -> INVESTIGATION ->
    EVIDENCE -> VALIDATION -> FINDING pipeline (Section 23): "Findings" in
    the UI is just this same table filtered to status=VALIDATED, not a
    separate table that could drift out of sync with the investigation it
    came from.
    """

    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    access_control_scenario_id: Mapped[int | None] = mapped_column(
        ForeignKey("access_control_scenarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Versioned, non-secret evidence context preserved if the scenario is
    # later edited or deleted. It is created canonically by the backend.
    access_control_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)

    title: Mapped[str] = mapped_column(String(300))
    target: Mapped[str] = mapped_column(String(500), default="")
    endpoint: Mapped[str] = mapped_column(String(500), default="")

    status: Mapped[InvestigationStatus] = mapped_column(Enum(InvestigationStatus), default=InvestigationStatus.OPEN)
    source: Mapped[InvestigationSource] = mapped_column(Enum(InvestigationSource), default=InvestigationSource.MANUAL)
    source_reference: Mapped[dict] = mapped_column(JSON, default=dict)

    ai_notes: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[int] = mapped_column(Integer, default=0)

    linked_transaction_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    linked_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    notes: Mapped[str] = mapped_column(Text, default="")

    # {question_key: true | false | null} - see FALSE_POSITIVE_QUESTIONS above.
    false_positive_checklist: Mapped[dict] = mapped_column(JSON, default=dict)

    impact_observed: Mapped[str] = mapped_column(Text, default="")
    impact_potential: Mapped[str] = mapped_column(Text, default="")

    # Per-lab learning state keyed by the stable practice lab id. Practice
    # traffic remains isolated from target evidence, while the investigation
    # remembers which contextual exercises the hunter started/completed.
    practice_progress: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    project = relationship("Project", back_populates="investigations")
    access_control_scenario = relationship("AccessControlScenario", back_populates="investigations")
    evidence_attachments = relationship("EvidenceAttachment", back_populates="investigation", cascade="all, delete-orphan")
    report = relationship("Report", back_populates="investigation", uselist=False, cascade="all, delete-orphan")
