from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from itertools import combinations
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api_mapper.categorize import normalize_path
from app.diff.models import AccessControlScenario
from app.diff.schemas import (
    AccessControlMatrixOut,
    AccessControlScenarioOut,
    ScenarioMatrixCellOut,
    ScenarioPairSelection,
    ScenarioTransactionOut,
)
from app.diff.service import _identity_marker, compare_transactions
from app.http.models import HttpTransaction
from app.investigations.models import Investigation, InvestigationSource
from app.projects.models import Project

MAX_SCENARIOS_PER_PROJECT = 20
MAX_TRANSACTIONS_PER_SCENARIO = 8


def clean_scenario_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Scenario name cannot be blank.")
    return cleaned


def validate_transaction_ids(db: Session, project_id: int, raw_ids: list[int]) -> list[int]:
    transaction_ids = list(dict.fromkeys(raw_ids))
    if len(transaction_ids) != len(raw_ids):
        raise HTTPException(status_code=422, detail="A scenario cannot contain duplicate transactions.")
    if not 2 <= len(transaction_ids) <= MAX_TRANSACTIONS_PER_SCENARIO:
        raise HTTPException(
            status_code=422,
            detail=f"Select between 2 and {MAX_TRANSACTIONS_PER_SCENARIO} transactions.",
        )
    found = {
        tx_id
        for (tx_id,) in db.query(HttpTransaction.id).filter(
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


def get_scenario_or_404(db: Session, project_id: int, scenario_id: int) -> AccessControlScenario:
    scenario = db.get(AccessControlScenario, scenario_id)
    if scenario is None or scenario.project_id != project_id:
        raise HTTPException(status_code=404, detail="Access-control scenario not found")
    return scenario


def _identity_fingerprint(tx: HttpTransaction) -> str:
    if tx.identity_profile_key:
        return f"profile:{tx.identity_profile_key}"
    marker = _identity_marker(tx.request_headers)
    return "manual:" + hashlib.sha256(marker.encode("utf-8")).hexdigest()


def build_matrix(db: Session, scenario: AccessControlScenario) -> AccessControlMatrixOut:
    rows = db.query(HttpTransaction).filter(
        HttpTransaction.project_id == scenario.project_id,
        HttpTransaction.id.in_(scenario.transaction_ids),
    ).all()
    by_id = {tx.id: tx for tx in rows}
    transactions = [by_id[tx_id] for tx_id in scenario.transaction_ids if tx_id in by_id]
    missing = [tx_id for tx_id in scenario.transaction_ids if tx_id not in by_id]

    summaries = [
        ScenarioTransactionOut(
            id=tx.id,
            method=tx.method,
            url=tx.url,
            normalized_pattern=normalize_path(urlsplit(tx.url).path or "/"),
            identity_name=tx.identity_profile_name or "Manual / unnamed credentials",
            identity_profile_id=tx.identity_profile_id,
            controlled_identity=bool(tx.identity_profile_key),
            status_code=tx.status_code,
            error=bool(tx.error),
        )
        for tx in transactions
    ]
    cells: list[ScenarioMatrixCellOut] = []
    for tx_a, tx_b in combinations(transactions, 2):
        result = compare_transactions(tx_a, tx_b)
        cells.append(ScenarioMatrixCellOut(
            transaction_a_id=tx_a.id,
            transaction_b_id=tx_b.id,
            same_endpoint_pattern=result.same_endpoint_pattern,
            same_identity=result.same_identity,
            status_match=result.status_match,
            confidence=result.finding.confidence,
            category=result.finding.category,
        ))

    warnings: list[str] = []
    if missing:
        warnings.append(
            "Some captured requests are no longer available: " + ", ".join(f"#{tx_id}" for tx_id in missing) + "."
        )
    patterns = {summary.normalized_pattern for summary in summaries}
    if len(patterns) > 1:
        warnings.append("The scenario contains multiple endpoint patterns; cross-pattern cells are not comparable.")
    if len({_identity_fingerprint(tx) for tx in transactions}) < 2:
        warnings.append("All available requests use the same identity; this scenario cannot test authorization boundaries.")
    if any(tx.identity_profile_key is None for tx in transactions):
        warnings.append("At least one request lacks controlled-profile attribution; identity matching falls back to headers.")
    if any(tx.error for tx in transactions):
        warnings.append("At least one request failed before receiving a response and cannot provide comparison evidence.")
    if len(transactions) < 2:
        warnings.append("Fewer than two captured requests remain; update or delete this scenario.")

    return AccessControlMatrixOut(
        scenario=AccessControlScenarioOut.model_validate(scenario),
        transactions=summaries,
        cells=cells,
        warnings=warnings,
    )


def build_investigation_from_scenario(
    db: Session,
    project: Project,
    scenario: AccessControlScenario,
    selected_pairs: list[ScenarioPairSelection],
    title: str | None = None,
) -> Investigation:
    """Create a canonical, non-secret snapshot from selected matrix cells."""
    matrix = build_matrix(db, scenario)
    cell_by_pair = {
        frozenset((cell.transaction_a_id, cell.transaction_b_id)): cell
        for cell in matrix.cells
    }
    summaries = {tx.id: tx for tx in matrix.transactions}
    seen: set[frozenset[int]] = set()
    selected_cells: list[dict] = []
    linked_transaction_ids: list[int] = []

    for selection in selected_pairs:
        pair = frozenset((selection.transaction_a_id, selection.transaction_b_id))
        if len(pair) != 2:
            raise HTTPException(status_code=422, detail="A comparison pair must contain two different transactions.")
        if pair in seen:
            raise HTTPException(status_code=422, detail="The selected comparison list contains a duplicate pair.")
        cell = cell_by_pair.get(pair)
        tx_a = summaries.get(selection.transaction_a_id)
        tx_b = summaries.get(selection.transaction_b_id)
        if cell is None or tx_a is None or tx_b is None:
            raise HTTPException(
                status_code=422,
                detail="Every selected comparison must reference two currently available requests in this scenario.",
            )
        seen.add(pair)
        for tx_id in (tx_a.id, tx_b.id):
            if tx_id not in linked_transaction_ids:
                linked_transaction_ids.append(tx_id)
        selected_cells.append({
            "transaction_a_id": tx_a.id,
            "transaction_b_id": tx_b.id,
            "identity_a": tx_a.identity_name,
            "identity_b": tx_b.identity_name,
            "identity_basis": (
                "controlled profiles"
                if tx_a.controlled_identity and tx_b.controlled_identity
                else "Authorization/Cookie headers"
            ),
            "url_a": tx_a.url,
            "url_b": tx_b.url,
            "pattern_a": tx_a.normalized_pattern,
            "pattern_b": tx_b.normalized_pattern,
            "status_a": tx_a.status_code,
            "status_b": tx_b.status_code,
            "same_endpoint_pattern": cell.same_endpoint_pattern,
            "same_identity": cell.same_identity,
            "status_match": cell.status_match,
            "confidence": cell.confidence,
            "category": cell.category,
        })

    snapshot = {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "scenario_description": scenario.description,
        "warnings": matrix.warnings,
        "selected_cells": selected_cells,
    }
    patterns = {
        pattern
        for cell in selected_cells
        for pattern in (cell["pattern_a"], cell["pattern_b"])
    }
    categories = sorted({cell["category"] for cell in selected_cells})
    warning_note = " ".join(matrix.warnings)
    ai_notes = (
        f"Access-control scenario '{scenario.name}' captured {len(selected_cells)} selected comparison pair(s). "
        f"Matrix categories: {', '.join(categories)}. {warning_note}"
    ).strip()
    resolved_title = title.strip() if title is not None else f"Access-control review: {scenario.name}"
    if not resolved_title:
        raise HTTPException(status_code=422, detail="Investigation title cannot be blank.")
    return Investigation(
        project_id=project.id,
        access_control_scenario_id=scenario.id,
        access_control_snapshot=snapshot,
        title=resolved_title,
        target=project.target,
        endpoint=next(iter(patterns)) if len(patterns) == 1 else "",
        source=InvestigationSource.DIFF_RESULT,
        source_reference={
            "kind": "access_control_scenario",
            "scenario_id": scenario.id,
            "snapshot_schema_version": 1,
            "selected_pairs": [
                [cell["transaction_a_id"], cell["transaction_b_id"]] for cell in selected_cells
            ],
        },
        ai_notes=ai_notes,
        confidence=max(cell["confidence"] for cell in selected_cells),
        linked_transaction_ids=linked_transaction_ids,
    )
