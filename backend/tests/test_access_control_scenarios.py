import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.core.database import Base
from app.diff.models import AccessControlScenario
from app.diff.router import create_scenario, delete_scenario, get_scenario_matrix, list_scenarios, update_scenario
from app.diff.scenario_service import build_investigation_from_scenario, build_matrix, validate_transaction_ids
from app.diff.schemas import AccessControlScenarioCreate, AccessControlScenarioUpdate, ScenarioPairSelection
from app.http.models import HttpTransaction
from app.evidence.service import build_evidence_package
from app.projects.models import Project


def _transaction(project_id: int, **overrides) -> HttpTransaction:
    values = dict(
        project_id=project_id,
        identity_profile_id=None,
        identity_profile_key="account-a",
        identity_profile_name="Account A",
        profile_header_names=["Authorization"],
        method="GET",
        url="https://api.example.com/orders/1",
        request_headers={"Authorization": "Bearer secret"},
        request_body=None,
        status_code=200,
        response_headers={"content-type": "application/json"},
        response_cookies=[],
        response_body='{"id":1,"owner":"alice"}',
        response_body_truncated=False,
        response_size_bytes=24,
        timing_ms=5.0,
        technologies=[],
        interesting_indicators=[],
        error=None,
    )
    values.update(overrides)
    return HttpTransaction(**values)


@pytest.fixture
def scenario_db():
    db_engine = create_engine("sqlite:///:memory:")

    @event.listens_for(db_engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(db_engine)
    with Session(db_engine) as db:
        project = Project(name="Program", target="example.com", allowed_domains=["example.com"])
        db.add(project)
        db.commit()
        yield db, project.id


def test_matrix_builds_every_pair_without_replaying_requests(scenario_db):
    db, project_id = scenario_db
    transactions = [
        _transaction(project_id),
        _transaction(
            project_id,
            url="https://api.example.com/orders/2",
            identity_profile_key="account-b",
            identity_profile_name="Account B",
            response_body='{"id":2,"owner":"bob"}',
        ),
        _transaction(
            project_id,
            url="https://api.example.com/users/1",
            identity_profile_key="account-b",
            identity_profile_name="Account B",
        ),
    ]
    db.add_all(transactions)
    db.commit()
    scenario = AccessControlScenario(
        project_id=project_id,
        name="Ownership matrix",
        transaction_ids=[tx.id for tx in transactions],
    )
    db.add(scenario)
    db.commit()

    matrix = build_matrix(db, scenario)

    assert len(matrix.transactions) == 3
    assert len(matrix.cells) == 3
    assert any(cell.confidence >= 60 for cell in matrix.cells if cell.same_endpoint_pattern)
    assert any("multiple endpoint patterns" in warning for warning in matrix.warnings)


def test_matrix_explains_same_identity_and_missing_profile_attribution(scenario_db):
    db, project_id = scenario_db
    tx_a = _transaction(project_id, identity_profile_key=None, identity_profile_name=None, request_headers={})
    tx_b = _transaction(
        project_id,
        url="https://api.example.com/orders/2",
        identity_profile_key=None,
        identity_profile_name=None,
        request_headers={},
    )
    db.add_all([tx_a, tx_b])
    db.commit()
    scenario = AccessControlScenario(
        project_id=project_id,
        name="Manual setup",
        transaction_ids=[tx_a.id, tx_b.id],
    )
    db.add(scenario)
    db.commit()

    matrix = build_matrix(db, scenario)

    assert matrix.cells[0].same_identity is True
    assert any("same identity" in warning for warning in matrix.warnings)
    assert any("falls back to headers" in warning for warning in matrix.warnings)


def test_scenario_validation_rejects_duplicates_and_cross_project_ids(scenario_db):
    db, project_id = scenario_db
    tx = _transaction(project_id)
    db.add(tx)
    db.commit()

    with pytest.raises(HTTPException, match="duplicate"):
        validate_transaction_ids(db, project_id, [tx.id, tx.id])
    with pytest.raises(HTTPException, match="not found in this project"):
        validate_transaction_ids(db, project_id, [tx.id, 99999])


def test_matrix_reports_transaction_removed_by_retention(scenario_db):
    db, project_id = scenario_db
    tx_a = _transaction(project_id)
    tx_b = _transaction(project_id, url="https://api.example.com/orders/2")
    db.add_all([tx_a, tx_b])
    db.commit()
    scenario = AccessControlScenario(
        project_id=project_id,
        name="Retention case",
        transaction_ids=[tx_a.id, tx_b.id],
    )
    db.add(scenario)
    db.commit()
    removed_id = tx_b.id
    db.delete(tx_b)
    db.commit()

    matrix = build_matrix(db, scenario)

    assert len(matrix.transactions) == 1
    assert any(f"#{removed_id}" in warning for warning in matrix.warnings)
    assert any("Fewer than two" in warning for warning in matrix.warnings)


def test_scenario_crud_keeps_transactions_untouched(scenario_db):
    db, project_id = scenario_db
    tx_a = _transaction(project_id)
    tx_b = _transaction(
        project_id,
        url="https://api.example.com/orders/2",
        identity_profile_key="account-b",
        identity_profile_name="Account B",
    )
    db.add_all([tx_a, tx_b])
    db.commit()

    scenario = create_scenario(
        project_id,
        AccessControlScenarioCreate(
            name="  Orders boundary  ",
            description="  Standard users  ",
            transaction_ids=[tx_a.id, tx_b.id],
        ),
        db,
    )
    assert scenario.name == "Orders boundary"
    assert list_scenarios(project_id, db)[0].id == scenario.id
    assert len(get_scenario_matrix(project_id, scenario.id, db).cells) == 1

    updated = update_scenario(
        project_id,
        scenario.id,
        AccessControlScenarioUpdate(description="Two controlled accounts"),
        db,
    )
    assert updated.description == "Two controlled accounts"

    response = delete_scenario(project_id, scenario.id, db)
    assert response.status_code == 204
    assert db.get(HttpTransaction, tx_a.id) is not None
    assert db.get(HttpTransaction, tx_b.id) is not None


def test_scenario_investigation_snapshot_survives_scenario_deletion(scenario_db):
    db, project_id = scenario_db
    project = db.get(Project, project_id)
    tx_a = _transaction(project_id)
    tx_b = _transaction(
        project_id,
        url="https://api.example.com/orders/2",
        identity_profile_key="account-b",
        identity_profile_name="Account B",
        request_headers={"Authorization": "Bearer another-secret"},
    )
    db.add_all([tx_a, tx_b])
    db.commit()
    scenario = AccessControlScenario(
        project_id=project_id,
        name="Durable ownership test",
        description="Two authorized test accounts",
        transaction_ids=[tx_a.id, tx_b.id],
    )
    db.add(scenario)
    db.commit()

    investigation = build_investigation_from_scenario(
        db,
        project,
        scenario,
        [ScenarioPairSelection(transaction_a_id=tx_a.id, transaction_b_id=tx_b.id)],
    )
    db.add(investigation)
    db.commit()
    investigation_id = investigation.id
    serialized_snapshot = str(investigation.access_control_snapshot)

    assert investigation.linked_transaction_ids == [tx_a.id, tx_b.id]
    assert investigation.access_control_snapshot["schema_version"] == 1
    assert investigation.access_control_snapshot["selected_cells"][0]["identity_a"] == "Account A"
    assert "Bearer secret" not in serialized_snapshot
    assert "another-secret" not in serialized_snapshot

    package = build_evidence_package(db, investigation)
    assert package.access_control_snapshot["scenario_name"] == "Durable ownership test"
    assert [tx.identity_profile_name for tx in package.transactions] == ["Account A", "Account B"]
    assert "Bearer secret" not in str(package.model_dump())

    db.delete(scenario)
    db.commit()
    db.expire_all()
    restored = db.get(type(investigation), investigation_id)
    assert restored.access_control_scenario_id is None
    assert restored.access_control_snapshot["scenario_name"] == "Durable ownership test"


def test_scenario_investigation_rejects_unselected_matrix_pair(scenario_db):
    db, project_id = scenario_db
    project = db.get(Project, project_id)
    tx_a = _transaction(project_id)
    tx_b = _transaction(project_id, url="https://api.example.com/orders/2")
    db.add_all([tx_a, tx_b])
    db.commit()
    scenario = AccessControlScenario(
        project_id=project_id,
        name="Canonical selection",
        transaction_ids=[tx_a.id, tx_b.id],
    )
    db.add(scenario)
    db.commit()

    with pytest.raises(HTTPException, match="currently available requests"):
        build_investigation_from_scenario(
            db,
            project,
            scenario,
            [ScenarioPairSelection(transaction_a_id=tx_a.id, transaction_b_id=99999)],
        )


def test_pre_alembic_bridge_adds_scenario_snapshot_columns(monkeypatch):
    from app.core import database

    legacy_engine = create_engine("sqlite:///:memory:")
    with legacy_engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE access_control_scenarios (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE investigations (id INTEGER PRIMARY KEY)")
    monkeypatch.setattr(database, "engine", legacy_engine)

    database._add_legacy_scenario_investigation_columns()

    with legacy_engine.connect() as connection:
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(investigations)")}
        indexes = {row[1] for row in connection.exec_driver_sql("PRAGMA index_list(investigations)")}
    assert {"access_control_scenario_id", "access_control_snapshot"}.issubset(columns)
    assert "ix_investigations_access_control_scenario_id" in indexes
