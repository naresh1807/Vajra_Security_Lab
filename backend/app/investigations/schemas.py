from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.investigations.models import InvestigationSource, InvestigationStatus


class InvestigationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    target: str = ""
    endpoint: str = ""
    source: InvestigationSource = InvestigationSource.MANUAL
    source_reference: dict = Field(default_factory=dict)
    ai_notes: str = ""
    confidence: int = Field(default=0, ge=0, le=100)
    linked_transaction_ids: list[int] = Field(default_factory=list, max_length=100)
    linked_asset_id: int | None = None


class InvestigationUpdate(BaseModel):
    title: str | None = None
    target: str | None = None
    endpoint: str | None = None
    status: InvestigationStatus | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)
    linked_transaction_ids: list[int] | None = Field(default=None, max_length=100)
    notes: str | None = None
    false_positive_checklist: dict[str, bool | None] | None = None
    impact_observed: str | None = None
    impact_potential: str | None = None


class InvestigationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    target: str
    endpoint: str
    status: InvestigationStatus
    source: InvestigationSource
    source_reference: dict
    ai_notes: str
    confidence: int
    linked_transaction_ids: list[int]
    linked_asset_id: int | None
    access_control_scenario_id: int | None
    access_control_snapshot: dict
    notes: str
    false_positive_checklist: dict[str, bool | None]
    impact_observed: str
    impact_potential: str
    practice_progress: dict
    created_at: datetime
    updated_at: datetime

    # Computed, not stored - see investigations/service.py.
    missing_evidence: list[str] = Field(default_factory=list)
    false_positive_hint: str | None = None
    false_positive_questions: dict[str, str] = Field(default_factory=dict)
    recommended_practice_labs: list[str] = Field(default_factory=list)


class PracticeProgressUpdate(BaseModel):
    status: str = Field(pattern="^(started|completed)$")
