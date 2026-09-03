from pydantic import BaseModel


class AuthFlowEndpoint(BaseModel):
    method: str
    path: str
    sources: list[str]
    sample_url: str | None


class AuthFlowStage(BaseModel):
    key: str
    title: str
    why: str
    review_checks: list[str]
    observed: bool
    endpoints: list[AuthFlowEndpoint]


class AuthFlowOut(BaseModel):
    stages: list[AuthFlowStage]
    observed_stage_count: int
    total_stage_count: int
    review_focus: list[str]
    note: str
