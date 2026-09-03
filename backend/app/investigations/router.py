from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.investigations.models import Investigation, InvestigationStatus
from app.investigations.schemas import InvestigationCreate, InvestigationOut, InvestigationUpdate, PracticeProgressUpdate
from app.investigations.service import to_out
from app.http.models import HttpTransaction
from app.projects.models import Project

router = APIRouter(prefix="/api/projects/{project_id}/investigations", tags=["investigations"])


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_investigation_or_404(db: Session, project_id: int, inv_id: int) -> Investigation:
    inv = db.get(Investigation, inv_id)
    if inv is None or inv.project_id != project_id:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv


def _validated_transaction_ids(db: Session, project_id: int, raw_ids: list[int]) -> list[int]:
    transaction_ids = list(dict.fromkeys(raw_ids))
    if len(transaction_ids) != len(raw_ids):
        raise HTTPException(status_code=422, detail="Linked transaction IDs cannot contain duplicates.")
    if not transaction_ids:
        return []
    found = {
        tx_id for (tx_id,) in db.query(HttpTransaction.id).filter(
            HttpTransaction.project_id == project_id,
            HttpTransaction.id.in_(transaction_ids),
        )
    }
    missing = [tx_id for tx_id in transaction_ids if tx_id not in found]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Transactions not found in this project: {', '.join(map(str, missing))}.",
        )
    return transaction_ids


@router.post("", response_model=InvestigationOut, status_code=201)
def create_investigation(project_id: int, payload: InvestigationCreate, db: Session = Depends(get_db)) -> InvestigationOut:
    project = _get_project_or_404(db, project_id)
    fields = payload.model_dump()
    fields["linked_transaction_ids"] = _validated_transaction_ids(
        db, project_id, fields["linked_transaction_ids"]
    )
    inv = Investigation(project_id=project.id, **fields)
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return to_out(inv)


@router.get("", response_model=list[InvestigationOut])
def list_investigations(
    project_id: int, status: InvestigationStatus | None = None, db: Session = Depends(get_db)
) -> list[InvestigationOut]:
    _get_project_or_404(db, project_id)
    query = db.query(Investigation).filter(Investigation.project_id == project_id)
    if status is not None:
        query = query.filter(Investigation.status == status)
    investigations = query.order_by(Investigation.updated_at.desc()).all()
    return [to_out(inv) for inv in investigations]


@router.get("/{inv_id}", response_model=InvestigationOut)
def get_investigation(project_id: int, inv_id: int, db: Session = Depends(get_db)) -> InvestigationOut:
    _get_project_or_404(db, project_id)
    inv = _get_investigation_or_404(db, project_id, inv_id)
    return to_out(inv)


@router.patch("/{inv_id}", response_model=InvestigationOut)
def update_investigation(
    project_id: int, inv_id: int, payload: InvestigationUpdate, db: Session = Depends(get_db)
) -> InvestigationOut:
    _get_project_or_404(db, project_id)
    inv = _get_investigation_or_404(db, project_id, inv_id)
    fields = payload.model_dump(exclude_unset=True)
    if "linked_transaction_ids" in fields:
        fields["linked_transaction_ids"] = _validated_transaction_ids(
            db, project_id, fields["linked_transaction_ids"]
        )
    for field, value in fields.items():
        setattr(inv, field, value)
    db.commit()
    db.refresh(inv)
    return to_out(inv)


@router.put("/{inv_id}/practice/{lab_id}", response_model=InvestigationOut)
def update_practice_progress(
    project_id: int, inv_id: int, lab_id: str, payload: PracticeProgressUpdate, db: Session = Depends(get_db)
) -> InvestigationOut:
    from app.practice.labs import CATALOG_BY_ID

    _get_project_or_404(db, project_id)
    inv = _get_investigation_or_404(db, project_id, inv_id)
    if lab_id not in CATALOG_BY_ID:
        raise HTTPException(status_code=404, detail="Practice lab not found")
    progress = dict(inv.practice_progress or {})
    progress[lab_id] = payload.status
    inv.practice_progress = progress
    db.commit()
    db.refresh(inv)
    return to_out(inv)


@router.delete("/{inv_id}", status_code=204)
def delete_investigation(project_id: int, inv_id: int, db: Session = Depends(get_db)) -> None:
    _get_project_or_404(db, project_id)
    inv = _get_investigation_or_404(db, project_id, inv_id)
    db.delete(inv)
    db.commit()
