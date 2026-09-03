from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analyzer.checks import AnalyzerInput, Classification, count_by_classification, run_all_analyzers
from app.analyzer.metadata import analyze_public_metadata
from app.analyzer.schemas import AnalyzerFindingOut, AnalyzerReportOut, AnalyzerSummaryOut, NotableFindingOut
from app.core.database import get_db
from app.http.models import HttpTransaction
from app.projects.models import Project
from app.surface.models import PublicMetadataDocument

router = APIRouter(prefix="/api/projects/{project_id}/analyzer", tags=["analyzer"])


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _to_input(tx: HttpTransaction) -> AnalyzerInput:
    return AnalyzerInput(
        url=tx.url,
        status_code=tx.status_code,
        request_headers=tx.request_headers,
        response_headers=tx.response_headers,
        response_cookies=tx.response_cookies,
        body=tx.response_body or "",
    )


@router.get("/transactions/{tx_id}", response_model=AnalyzerReportOut)
def analyze_transaction(project_id: int, tx_id: int, db: Session = Depends(get_db)) -> AnalyzerReportOut:
    _get_project_or_404(db, project_id)
    tx = db.get(HttpTransaction, tx_id)
    if tx is None or tx.project_id != project_id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.error:
        raise HTTPException(status_code=422, detail="This transaction failed before a response was received - nothing to analyze.")

    findings = run_all_analyzers(_to_input(tx))
    return AnalyzerReportOut(
        transaction_id=tx.id,
        url=tx.url,
        findings=[AnalyzerFindingOut(**asdict(f)) for f in findings],
        counts=count_by_classification(findings),
    )


@router.get("/summary", response_model=AnalyzerSummaryOut)
def analyzer_summary(project_id: int, db: Session = Depends(get_db)) -> AnalyzerSummaryOut:
    _get_project_or_404(db, project_id)
    transactions = (
        db.query(HttpTransaction)
        .filter(HttpTransaction.project_id == project_id, HttpTransaction.error.is_(None))
        .all()
    )

    total_counts = {
        Classification.INFORMATIONAL: 0,
        Classification.INTERESTING: 0,
        Classification.NEEDS_REVIEW: 0,
        Classification.POTENTIAL_FINDING: 0,
    }
    notable: list[NotableFindingOut] = []

    for tx in transactions:
        findings = run_all_analyzers(_to_input(tx))
        counts = count_by_classification(findings)
        for k, v in counts.items():
            total_counts[k] += v
        for f in findings:
            if f.classification in (Classification.NEEDS_REVIEW, Classification.POTENTIAL_FINDING):
                notable.append(NotableFindingOut(transaction_id=tx.id, url=tx.url, finding=AnalyzerFindingOut(**asdict(f))))

    metadata_documents = (
        db.query(PublicMetadataDocument)
        .filter(
            PublicMetadataDocument.project_id == project_id,
            PublicMetadataDocument.status_code == 200,
            PublicMetadataDocument.error.is_(None),
        )
        .all()
    )
    for document in metadata_documents:
        findings = analyze_public_metadata(document)
        counts = count_by_classification(findings)
        for key, value in counts.items():
            total_counts[key] += value
        for finding in findings:
            if finding.classification in (Classification.NEEDS_REVIEW, Classification.POTENTIAL_FINDING):
                notable.append(NotableFindingOut(
                    transaction_id=None,
                    url=document.url,
                    source="public_metadata",
                    finding=AnalyzerFindingOut(**asdict(finding)),
                ))

    notable.sort(key=lambda n: 0 if n.finding.classification == Classification.POTENTIAL_FINDING else 1)

    return AnalyzerSummaryOut(
        transactions_analyzed=len(transactions),
        metadata_documents_analyzed=len(metadata_documents),
        counts=total_counts,
        notable_findings=notable[:50],
    )
