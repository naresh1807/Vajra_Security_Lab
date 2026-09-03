from pydantic import BaseModel


class TestTypeOut(BaseModel):
    key: str
    name: str
    definition: str
    how_to_set_up: list[str]
    signals_worth_a_finding: list[str]
    evidence_needed: list[str]


class WorkbenchIdentity(BaseModel):
    id: int
    name: str
    enabled: bool


class WorkbenchCapture(BaseModel):
    transaction_id: int
    method: str
    url: str
    identity_name: str
    identity_profile_id: int | None
    controlled_identity: bool
    status_code: int | None
    error: bool


class WorkbenchSuggestedPair(BaseModel):
    transaction_a_id: int
    transaction_b_id: int
    identity_a: str
    identity_b: str


class WorkbenchEndpointGroup(BaseModel):
    pattern: str
    methods: list[str]
    has_object_identifier: bool
    distinct_identities: int
    distinct_object_identifiers: int
    capture_count: int
    captures: list[WorkbenchCapture]
    suggested_pairs: list[WorkbenchSuggestedPair]
    readiness: str
    next_step: str


class AccessControlWorkbenchOut(BaseModel):
    test_types: list[TestTypeOut]
    identities: list[WorkbenchIdentity]
    endpoint_groups: list[WorkbenchEndpointGroup]
    ready_endpoint_count: int
    setup_warnings: list[str]
    note: str
