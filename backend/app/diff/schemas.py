from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HeaderDiffEntry(BaseModel):
    header: str
    value_a: str | None
    value_b: str | None


class DiffFindingOut(BaseModel):
    confidence: int
    category: str
    notes: list[str]


class DiffResultOut(BaseModel):
    transaction_a_id: int
    transaction_b_id: int
    url_a: str
    url_b: str
    normalized_pattern: str | None
    same_endpoint_pattern: bool
    same_identity: bool
    identity_a: str
    identity_b: str
    identity_basis: str
    status_a: int | None
    status_b: int | None
    status_match: bool
    length_a: int | None
    length_b: int | None
    header_differences: list[HeaderDiffEntry]
    body_keys_only_in_a: list[str]
    body_keys_only_in_b: list[str]
    body_common_keys: list[str]
    finding: DiffFindingOut


class AccessControlScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=1000)
    transaction_ids: list[int] = Field(min_length=2, max_length=8)


class AccessControlScenarioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    transaction_ids: list[int] | None = Field(default=None, min_length=2, max_length=8)


class AccessControlScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: str
    transaction_ids: list[int]
    created_at: datetime
    updated_at: datetime


class ScenarioTransactionOut(BaseModel):
    id: int
    method: str
    url: str
    normalized_pattern: str
    identity_name: str
    identity_profile_id: int | None
    controlled_identity: bool
    status_code: int | None
    error: bool


class ScenarioMatrixCellOut(BaseModel):
    transaction_a_id: int
    transaction_b_id: int
    same_endpoint_pattern: bool
    same_identity: bool
    status_match: bool
    confidence: int
    category: str


class AccessControlMatrixOut(BaseModel):
    scenario: AccessControlScenarioOut
    transactions: list[ScenarioTransactionOut]
    cells: list[ScenarioMatrixCellOut]
    warnings: list[str]


class ScenarioPairSelection(BaseModel):
    transaction_a_id: int = Field(ge=1)
    transaction_b_id: int = Field(ge=1)


class ScenarioInvestigationCreate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    selected_pairs: list[ScenarioPairSelection] = Field(min_length=1, max_length=28)
