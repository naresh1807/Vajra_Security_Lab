from pydantic import BaseModel


class ExplainRequest(BaseModel):
    kind: str  # "asset" | "header"
    asset_id: int | None = None
    header_name: str | None = None


class ExplanationOut(BaseModel):
    what_found: str
    why_it_matters: str
    what_to_check: list[str]
    false_positive_notes: list[str]
    evidence_needed: list[str]
    mini_lesson_title: str | None = None
    mini_lesson: str | None = None


class FocusAreaOut(BaseModel):
    label: str
    detail: str
    route: str | None = None


class NextBestActionOut(BaseModel):
    headline: str
    reason: str
    cta_label: str | None = None
    cta_route: str | None = None
    focus_areas: list[FocusAreaOut] = []
    recommended_asset_id: int | None = None
    recommended_hostname: str | None = None
    alternatives: list[str]


class AskRequest(BaseModel):
    question: str
    investigation_id: int | None = None
    asset_id: int | None = None
    transaction_id: int | None = None


class AskResponse(BaseModel):
    answer: str
    provider: str
