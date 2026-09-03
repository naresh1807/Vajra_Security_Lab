from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.diff.models import AccessControlScenario
from app.diff.scenario_service import (
    MAX_SCENARIOS_PER_PROJECT,
    build_matrix,
    build_investigation_from_scenario,
    clean_scenario_name,
    get_scenario_or_404,
    validate_transaction_ids,
)
from app.diff.schemas import (
    AccessControlMatrixOut,
    AccessControlScenarioCreate,
    AccessControlScenarioOut,
    AccessControlScenarioUpdate,
    DiffResultOut,
    ScenarioInvestigationCreate,
)
from app.diff.service import compare_transactions
from app.http.models import HttpTransaction
from app.investigations.models import Investigation
from app.investigations.schemas import InvestigationOut
from app.investigations.service import to_out as investigation_out
from app.projects.models import Project

router = APIRouter(prefix="/api/projects/{project_id}/diff", tags=["diff"])


def _project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/compare", response_model=DiffResultOut)
def compare(
    project_id: int,
    transaction_a_id: int = Query(...),
    transaction_b_id: int = Query(...),
    db: Session = Depends(get_db),
) -> DiffResultOut:
    _project_or_404(db, project_id)

    tx_a = db.get(HttpTransaction, transaction_a_id)
    tx_b = db.get(HttpTransaction, transaction_b_id)
    if tx_a is None or tx_a.project_id != project_id:
        raise HTTPException(status_code=404, detail="Request A not found in this project")
    if tx_b is None or tx_b.project_id != project_id:
        raise HTTPException(status_code=404, detail="Request B not found in this project")

    return compare_transactions(tx_a, tx_b)


@router.get("/scenarios", response_model=list[AccessControlScenarioOut])
def list_scenarios(project_id: int, db: Session = Depends(get_db)) -> list[AccessControlScenario]:
    _project_or_404(db, project_id)
    return db.query(AccessControlScenario).filter(
        AccessControlScenario.project_id == project_id
    ).order_by(AccessControlScenario.updated_at.desc()).all()


@router.post("/scenarios", response_model=AccessControlScenarioOut, status_code=201)
def create_scenario(
    project_id: int,
    payload: AccessControlScenarioCreate,
    db: Session = Depends(get_db),
) -> AccessControlScenario:
    _project_or_404(db, project_id)
    if db.query(AccessControlScenario).filter(AccessControlScenario.project_id == project_id).count() >= MAX_SCENARIOS_PER_PROJECT:
        raise HTTPException(
            status_code=409,
            detail=f"A project can contain at most {MAX_SCENARIOS_PER_PROJECT} access-control scenarios.",
        )
    scenario = AccessControlScenario(
        project_id=project_id,
        name=clean_scenario_name(payload.name),
        description=payload.description.strip(),
        transaction_ids=validate_transaction_ids(db, project_id, payload.transaction_ids),
    )
    db.add(scenario)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A scenario with this name already exists in the project.") from exc
    db.refresh(scenario)
    return scenario


@router.get("/scenarios/{scenario_id}", response_model=AccessControlMatrixOut)
def get_scenario_matrix(
    project_id: int,
    scenario_id: int,
    db: Session = Depends(get_db),
) -> AccessControlMatrixOut:
    _project_or_404(db, project_id)
    return build_matrix(db, get_scenario_or_404(db, project_id, scenario_id))


@router.post("/scenarios/{scenario_id}/investigation", response_model=InvestigationOut, status_code=201)
def create_scenario_investigation(
    project_id: int,
    scenario_id: int,
    payload: ScenarioInvestigationCreate,
    db: Session = Depends(get_db),
) -> InvestigationOut:
    project = _project_or_404(db, project_id)
    scenario = get_scenario_or_404(db, project_id, scenario_id)
    investigation: Investigation = build_investigation_from_scenario(
        db,
        project,
        scenario,
        payload.selected_pairs,
        payload.title,
    )
    db.add(investigation)
    db.commit()
    db.refresh(investigation)
    return investigation_out(investigation)


@router.patch("/scenarios/{scenario_id}", response_model=AccessControlScenarioOut)
def update_scenario(
    project_id: int,
    scenario_id: int,
    payload: AccessControlScenarioUpdate,
    db: Session = Depends(get_db),
) -> AccessControlScenario:
    _project_or_404(db, project_id)
    scenario = get_scenario_or_404(db, project_id, scenario_id)
    if payload.name is not None:
        scenario.name = clean_scenario_name(payload.name)
    if payload.description is not None:
        scenario.description = payload.description.strip()
    if payload.transaction_ids is not None:
        scenario.transaction_ids = validate_transaction_ids(db, project_id, payload.transaction_ids)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A scenario with this name already exists in the project.") from exc
    db.refresh(scenario)
    return scenario


@router.delete("/scenarios/{scenario_id}", status_code=204)
def delete_scenario(project_id: int, scenario_id: int, db: Session = Depends(get_db)) -> Response:
    _project_or_404(db, project_id)
    scenario = get_scenario_or_404(db, project_id, scenario_id)
    db.delete(scenario)
    db.commit()
    return Response(status_code=204)
