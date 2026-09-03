"""
Vajra Next-Best-Action Engine (Section 26).

Given the project's real state, it names the single most useful next
move and the shortcut to get there - "the beginner never gets lost".
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.copilot.next_action import compute_next_best_action
from app.core.database import Base
from app.investigations.models import Investigation, InvestigationStatus
from app.projects.models import Project
from app.recon.models import Asset
from app.reports.models import Report
from app.surface.models import DiscoveredEndpoint


def _project(db: Session) -> Project:
    project = Project(
        name="NBA", target="example.com", allowed_domains=["example.com"],
        allowed_subdomains=[], excluded_assets=[], rate_limit_rps=1.0,
    )
    db.add(project)
    db.flush()
    return project


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_empty_project_says_run_recon():
    with _db() as db:
        project = _project(db)
        db.commit()
        nba = compute_next_best_action(db, project.id)
    assert "Run recon" in nba["headline"]
    assert nba["cta_route"] is None


def test_high_priority_asset_with_no_investigations_is_recommended():
    with _db() as db:
        project = _project(db)
        db.add(Asset(project_id=project.id, hostname="api.example.com", source="dns",
                     priority_score=85, priority_category="api", priority_reasons=["API host"]))
        db.add(Asset(project_id=project.id, hostname="www.example.com", source="dns", priority_score=10))
        db.commit()
        nba = compute_next_best_action(db, project.id)
    assert nba["headline"] == "Investigate api.example.com"
    assert nba["recommended_hostname"] == "api.example.com"
    assert nba["alternatives"]


def test_object_id_endpoints_route_to_the_access_control_workbench():
    with _db() as db:
        project = _project(db)
        db.add(Asset(project_id=project.id, hostname="api.example.com", source="dns", priority_score=5, reviewed=True))
        db.add(DiscoveredEndpoint(
            project_id=project.id, url="https://api.example.com/api/orders/5",
            normalized_url="https://api.example.com/api/orders/5", hostname="api.example.com",
            path="/api/orders/5", method="GET", source="wayback",
        ))
        db.commit()
        nba = compute_next_best_action(db, project.id)
    assert nba["headline"] == "Test object-level access control"
    assert nba["cta_route"] == "access-control"
    assert any(area["route"] == "access-control" for area in nba["focus_areas"])


def test_auth_flow_endpoints_route_to_the_auth_flow_analyzer():
    with _db() as db:
        project = _project(db)
        db.add(Asset(project_id=project.id, hostname="example.com", source="dns", priority_score=5, reviewed=True))
        db.add(DiscoveredEndpoint(
            project_id=project.id, url="https://example.com/api/auth/login",
            normalized_url="https://example.com/api/auth/login", hostname="example.com",
            path="/api/auth/login", method="POST", source="wayback",
        ))
        db.commit()
        nba = compute_next_best_action(db, project.id)
    assert nba["headline"] == "Review the authentication flow"
    assert nba["cta_route"] == "auth-flow"


def test_validated_finding_without_a_report_prompts_the_report_generator():
    with _db() as db:
        project = _project(db)
        db.add(Asset(project_id=project.id, hostname="example.com", source="dns", priority_score=5, reviewed=True))
        inv = Investigation(project_id=project.id, title="Confirmed IDOR on orders",
                            status=InvestigationStatus.VALIDATED, linked_transaction_ids=[1, 2])
        db.add(inv)
        db.commit()
        nba = compute_next_best_action(db, project.id)
    assert nba["headline"].startswith("Generate the report")
    assert nba["cta_route"] == f"investigations/{inv.id}/report"

    # ...and once the report exists, it stops recommending that.
    with _db() as db:
        project = _project(db)
        db.add(Asset(project_id=project.id, hostname="example.com", source="dns", priority_score=5, reviewed=True))
        inv = Investigation(project_id=project.id, title="Confirmed IDOR", status=InvestigationStatus.VALIDATED,
                            linked_transaction_ids=[1, 2])
        db.add(inv)
        db.flush()
        db.add(Report(investigation_id=inv.id, summary="x"))
        db.commit()
        nba = compute_next_best_action(db, project.id)
    assert not nba["headline"].startswith("Generate the report")
