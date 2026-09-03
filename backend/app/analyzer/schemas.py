from pydantic import BaseModel, Field


class AnalyzerFindingOut(BaseModel):
    category: str
    classification: str
    title: str
    description: str
    evidence: list[str] = Field(default_factory=list)


class AnalyzerReportOut(BaseModel):
    transaction_id: int
    url: str
    findings: list[AnalyzerFindingOut]
    counts: dict[str, int]


class NotableFindingOut(BaseModel):
    transaction_id: int | None
    url: str
    source: str = "http_transaction"
    finding: AnalyzerFindingOut


class AnalyzerSummaryOut(BaseModel):
    transactions_analyzed: int
    metadata_documents_analyzed: int = 0
    counts: dict[str, int]
    notable_findings: list[NotableFindingOut]
