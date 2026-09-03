from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.scopeguard.models import ScopeDecision


class ScopeCheckRequest(BaseModel):
    target: str


class ScopeCheckResponse(BaseModel):
    target_input: str
    normalized_target: str
    decision: ScopeDecision
    reason: str


class ScopeAuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_input: str
    normalized_target: str
    decision: ScopeDecision
    reason: str
    operation: str
    created_at: datetime
