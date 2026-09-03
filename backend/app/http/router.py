from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.http.models import HttpTransaction
from app.http.schemas import HttpTransactionOut, SendRequestPayload
from app.http.service import ScopeBlockedError, send_http_request
from app.identities.models import IdentityProfile
from app.identities.service import get_profile_or_404, merge_profile_headers
from app.projects.models import Project

router = APIRouter(prefix="/api/projects/{project_id}/http", tags=["http"])


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _transaction_out(tx: HttpTransaction) -> HttpTransactionOut:
    """Serialize a transaction without disclosing stored identity secrets."""
    result = HttpTransactionOut.model_validate(tx)
    secret_names = {name.lower() for name in (tx.profile_header_names or [])}
    safe_headers = {
        name: "[STORED IDENTITY SECRET]" if name.lower() in secret_names else value
        for name, value in result.request_headers.items()
    }
    return result.model_copy(update={"request_headers": safe_headers})


@router.post("/send", response_model=HttpTransactionOut, status_code=201)
async def send_request(project_id: int, payload: SendRequestPayload, db: Session = Depends(get_db)) -> HttpTransactionOut:
    project = _get_project_or_404(db, project_id)

    profile: IdentityProfile | None = None
    headers = payload.headers
    if payload.identity_profile_id is not None:
        profile = get_profile_or_404(db, project_id, payload.identity_profile_id)
        if not profile.enabled:
            raise HTTPException(status_code=409, detail="The selected identity profile is disabled.")
        headers = merge_profile_headers(headers, profile.secret_headers)

    try:
        fields = await send_http_request(
            db,
            project,
            payload.method,
            payload.url,
            headers,
            payload.body,
            sensitive_header_names=set(profile.secret_headers) if profile else None,
        )
    except ScopeBlockedError as exc:
        raise HTTPException(
            status_code=403,
            detail=f"Vajra ScopeGuard blocked this request ({exc.decision.value}): {exc.reason}",
        ) from exc

    tx = HttpTransaction(
        project_id=project.id,
        identity_profile_id=profile.id if profile else None,
        identity_profile_key=profile.identity_key if profile else None,
        identity_profile_name=profile.name if profile else None,
        profile_header_names=sorted(profile.secret_headers, key=str.lower) if profile else [],
        **fields,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return _transaction_out(tx)


@router.get("/transactions", response_model=list[HttpTransactionOut])
def list_transactions(project_id: int, db: Session = Depends(get_db)) -> list[HttpTransactionOut]:
    _get_project_or_404(db, project_id)
    transactions = (
        db.query(HttpTransaction)
        .filter(HttpTransaction.project_id == project_id)
        .order_by(HttpTransaction.created_at.desc())
        .limit(200)
        .all()
    )
    return [_transaction_out(tx) for tx in transactions]


@router.get("/transactions/{tx_id}", response_model=HttpTransactionOut)
def get_transaction(project_id: int, tx_id: int, db: Session = Depends(get_db)) -> HttpTransactionOut:
    _get_project_or_404(db, project_id)
    tx = db.get(HttpTransaction, tx_id)
    if tx is None or tx.project_id != project_id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _transaction_out(tx)
