from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.copilot.knowledge import ask_hunt_copilot, default_provider
from app.copilot.next_action import compute_next_best_action
from app.copilot.schemas import AskRequest, AskResponse, ExplainRequest, ExplanationOut, NextBestActionOut
from app.core.database import get_db
from app.evidence.masking import mask_body, mask_cookies, mask_headers
from app.http.models import HttpTransaction
from app.investigations.models import Investigation
from app.projects.models import Project
from app.recon.models import Asset

router = APIRouter(tags=["copilot"])

MAX_CONTEXT_BODY_CHARS = 2000


@router.post("/api/copilot/explain", response_model=ExplanationOut)
def explain(payload: ExplainRequest, request: Request, db: Session = Depends(get_db)) -> ExplanationOut:
    if payload.kind == "asset":
        if payload.asset_id is None:
            raise HTTPException(status_code=400, detail="asset_id is required for kind='asset'")
        asset = db.get(Asset, payload.asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset not found")
        project = db.get(Project, asset.project_id)
        if project is None or project.owner_id != request.state.user_id:
            raise HTTPException(status_code=404, detail="Asset not found")
        explanation = default_provider.explain_asset(asset.hostname, asset.priority_category)
        return ExplanationOut(**explanation.__dict__)

    if payload.kind == "header":
        if not payload.header_name:
            raise HTTPException(status_code=400, detail="header_name is required for kind='header'")
        explanation = default_provider.explain_header(payload.header_name)
        if explanation is None:
            return ExplanationOut(
                what_found=f"The '{payload.header_name}' header.",
                why_it_matters="Vajra doesn't have a specific note for this header yet - inspect its value and compare it across requests.",
                what_to_check=["Compare this header's value across different sessions/roles."],
                false_positive_notes=[],
                evidence_needed=["The raw header value across compared requests."],
            )
        return ExplanationOut(**explanation.__dict__)

    raise HTTPException(status_code=400, detail="kind must be 'asset' or 'header'")


@router.get("/api/projects/{project_id}/copilot/next-best-action", response_model=NextBestActionOut)
def next_best_action(project_id: int, db: Session = Depends(get_db)) -> NextBestActionOut:
    """Vajra Next-Best-Action Engine (Section 26)."""
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return NextBestActionOut(**compute_next_best_action(db, project_id))


def _build_ask_context(db: Session, project_id: int, payload: AskRequest) -> dict:
    """Gathers real, already-collected data for whichever entity the question
    references - never fabricated. Any HTTP transaction included is masked
    (Section 31) before it ever leaves this process, live LLM call or not.
    """
    context: dict = {}

    if payload.investigation_id is not None:
        inv = db.get(Investigation, payload.investigation_id)
        if inv is not None and inv.project_id == project_id:
            context.update(
                {
                    "investigation_title": inv.title,
                    "investigation_target": inv.target,
                    "investigation_endpoint": inv.endpoint,
                    "investigation_status": inv.status.value,
                    "investigation_confidence": inv.confidence,
                    "investigation_ai_notes": inv.ai_notes,
                    "investigation_notes": inv.notes,
                    "investigation_impact_observed": inv.impact_observed,
                    "investigation_impact_potential": inv.impact_potential,
                }
            )

    if payload.asset_id is not None:
        asset = db.get(Asset, payload.asset_id)
        if asset is not None and asset.project_id == project_id:
            context.update(
                {
                    "asset_hostname": asset.hostname,
                    "asset_priority_category": asset.priority_category,
                    "asset_priority_score": asset.priority_score,
                    "asset_priority_reasons": ", ".join(asset.priority_reasons),
                    "asset_technologies": ", ".join(asset.technologies),
                    "asset_is_live": asset.is_live,
                    "asset_status_code": asset.status_code,
                }
            )

    if payload.transaction_id is not None:
        tx = db.get(HttpTransaction, payload.transaction_id)
        if tx is not None and tx.project_id == project_id:
            context.update(
                {
                    "transaction_method": tx.method,
                    "transaction_url": tx.url,
                    "transaction_status_code": tx.status_code,
                    # Request headers (Authorization, Cookie) are exactly where a real tested
                    # secret lives - mask them here too, not just the response side.
                    "transaction_request_headers": mask_headers(tx.request_headers),
                    "transaction_response_headers": mask_headers(tx.response_headers),
                    "transaction_response_cookies": mask_cookies(tx.response_cookies),
                    "transaction_response_body": (mask_body(tx.response_body) or "")[:MAX_CONTEXT_BODY_CHARS],
                }
            )

    return context


@router.post("/api/projects/{project_id}/copilot/ask", response_model=AskResponse)
async def ask(project_id: int, payload: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    """Vajra Hunt Copilot free-form chat (Section 25) - tries a live AI
    provider first, falls back to a plain, honest message if none is
    configured or reachable (see knowledge.ask_hunt_copilot)."""
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    context = _build_ask_context(db, project_id, payload)
    answer, provider = await ask_hunt_copilot(payload.question, context)
    return AskResponse(answer=answer, provider=provider)
