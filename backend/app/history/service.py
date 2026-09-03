from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from app.history.schemas import HuntEventOut, HuntHistoryOut
from app.http.models import HttpTransaction
from app.investigations.models import Investigation
from app.js_inspector.models import JsFile
from app.recon.models import Asset, ReconJob
from app.reports.models import Report
from app.scopeguard.models import ScopeAuditLog


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def build_hunt_history(db: Session, project_id: int, category: str | None, limit: int, offset: int) -> HuntHistoryOut:
    events: list[HuntEventOut] = []
    for row in db.query(ScopeAuditLog).filter(ScopeAuditLog.project_id == project_id):
        events.append(HuntEventOut(id=f"scope-{row.id}", category="scope", title=f"ScopeGuard: {_value(row.decision)}", detail=f"{row.operation} · {row.normalized_target or row.target_input} · {row.reason}", status=_value(row.decision), occurred_at=row.created_at))
    for row in db.query(ReconJob).filter(ReconJob.project_id == project_id):
        events.append(HuntEventOut(id=f"recon-{row.id}", category="recon", title=f"Recon job #{row.id}", detail=f"Stage: {_value(row.stage) if row.stage else 'not started'}" + (f" · {row.error}" if row.error else ""), status=_value(row.status), occurred_at=row.completed_at or row.started_at, href=f"/projects/{project_id}"))
    for row in db.query(Asset).filter(Asset.project_id == project_id):
        events.append(HuntEventOut(id=f"asset-{row.id}", category="asset", title=f"Asset discovered: {row.hostname}", detail=f"{_value(row.asset_type)} · priority {row.priority_score}", status="reviewed" if row.reviewed else "new", occurred_at=row.discovered_at, href=f"/projects/{project_id}"))
    for row in db.query(HttpTransaction).filter(HttpTransaction.project_id == project_id):
        status = "error" if row.error else str(row.status_code or "no_response")
        events.append(HuntEventOut(id=f"http-{row.id}", category="http", title=f"{row.method} request", detail=f"{row.url} · HTTP {status}", status=status, occurred_at=row.created_at, href=f"/projects/{project_id}/http?transactionId={row.id}"))
    for row in db.query(JsFile).filter(JsFile.project_id == project_id):
        events.append(HuntEventOut(id=f"js-{row.id}", category="javascript", title="JavaScript analyzed", detail=f"{row.url} · {len(row.findings)} findings", status="error" if row.error else str(row.status_code or "complete"), occurred_at=row.fetched_at, href=f"/projects/{project_id}/js"))
    investigations = db.query(Investigation).filter(Investigation.project_id == project_id).all()
    for row in investigations:
        events.append(HuntEventOut(id=f"investigation-{row.id}", category="investigation", title=row.title, detail=f"{_value(row.source)} · confidence {row.confidence}%", status=_value(row.status), occurred_at=row.updated_at, href=f"/projects/{project_id}/investigations/{row.id}"))
    investigation_ids = [row.id for row in investigations]
    if investigation_ids:
        for row in db.query(Report).filter(Report.investigation_id.in_(investigation_ids)):
            events.append(HuntEventOut(id=f"report-{row.id}", category="report", title=f"Report updated for investigation #{row.investigation_id}", detail="Report draft created or edited", status="draft", occurred_at=row.updated_at, href=f"/projects/{project_id}/investigations/{row.investigation_id}/report"))

    events.sort(key=lambda item: item.occurred_at, reverse=True)
    categories = dict(sorted(Counter(item.category for item in events).items()))
    filtered = [item for item in events if category is None or item.category == category]
    return HuntHistoryOut(events=filtered[offset:offset + limit], total=len(filtered), categories=categories)
