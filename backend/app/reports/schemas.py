from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReportUpdate(BaseModel):
    summary: str | None = None
    prerequisites: str | None = None
    steps_to_reproduce: str | None = None
    observed_behavior: str | None = None
    expected_behavior: str | None = None
    suggested_remediation: str | None = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investigation_id: int
    summary: str
    prerequisites: str
    steps_to_reproduce: str
    observed_behavior: str
    expected_behavior: str
    suggested_remediation: str
    created_at: datetime
    updated_at: datetime


class ReadinessCheck(BaseModel):
    label: str
    passed: bool
    points: int


class ReadinessOut(BaseModel):
    score: int
    checks: list[ReadinessCheck]
    missing: list[str]
