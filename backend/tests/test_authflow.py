"""
Vajra Authentication Flow Analyzer (Section 18).

The pure `assign_stage` rule, then `build_auth_flow` mapping real
project data (HTTP history, discovered endpoints, JS routes) onto the
canonical flow - and confirming it never fabricates a stage or a claim.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.authflow.service import build_auth_flow
from app.authflow.stages import FLOW_ORDER, assign_stage
from app.core.database import Base
from app.http.models import HttpTransaction
from app.js_inspector.models import FindingType, JsFile, JsFinding
from app.projects.models import Project
from app.surface.models import DiscoveredEndpoint


# --- assign_stage --------------------------------------------------------

def test_assign_stage_precedence_reset_beats_change_beats_login():
    assert assign_stage("POST", "/api/auth/forgot-password") == "password_reset"
    assert assign_stage("POST", "/api/account/change-password") == "password_change"
    assert assign_stage("POST", "/api/auth/login") == "login"


def test_assign_stage_logout_not_confused_with_login():
    assert assign_stage("POST", "/api/auth/logout") == "logout"


def test_assign_stage_delete_on_session_is_logout():
    assert assign_stage("DELETE", "/api/sessions/current") == "logout"


def test_assign_stage_token_and_verification_and_mfa():
    assert assign_stage("POST", "/oauth/token") == "session_issuance"
    assert assign_stage("GET", "/verify-email") == "email_verification"
    assert assign_stage("POST", "/api/2fa/verify") == "mfa"


def test_assign_stage_returns_none_for_unrelated_paths():
    assert assign_stage("GET", "/api/orders/42") is None
    assert assign_stage("GET", "/api/products") is None


# --- build_auth_flow ----------------------------------------------------

def _project(db: Session) -> Project:
    project = Project(
        name="AuthFlow", target="example.com", allowed_domains=["example.com"],
        allowed_subdomains=[], excluded_assets=[], rate_limit_rps=1.0,
    )
    db.add(project)
    db.flush()
    return project


def test_flow_always_returns_every_stage_in_order():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)
        db.commit()
        flow = build_auth_flow(db, project.id)

    assert [stage["key"] for stage in flow["stages"]] == list(FLOW_ORDER)
    assert all(stage["observed"] is False for stage in flow["stages"])
    assert flow["observed_stage_count"] == 0
    assert flow["review_focus"]  # non-empty even with nothing observed
    assert all(stage["review_checks"] for stage in flow["stages"])


def test_flow_maps_observed_endpoints_and_builds_focus():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)
        db.add(HttpTransaction(
            project_id=project.id, method="POST",
            url="https://api.example.com/api/v2/auth/login",
        ))
        db.add(DiscoveredEndpoint(
            project_id=project.id,
            url="https://api.example.com/api/v2/password/reset",
            normalized_url="https://api.example.com/api/v2/password/reset",
            hostname="api.example.com", path="/api/v2/password/reset", method="POST",
            source="openapi",
        ))
        js = JsFile(project_id=project.id, url="https://example.com/app.js")
        db.add(js)
        db.flush()
        db.add(JsFinding(js_file_id=js.id, finding_type=FindingType.API_ROUTE,
                         value="/api/v2/mfa/challenge"))
        db.commit()
        flow = build_auth_flow(db, project.id)

    stages = {stage["key"]: stage for stage in flow["stages"]}

    assert stages["login"]["observed"] is True
    assert stages["login"]["endpoints"][0]["method"] == "POST"
    assert stages["login"]["endpoints"][0]["sample_url"].endswith("/auth/login")
    assert stages["password_reset"]["observed"] is True
    assert "openapi" in stages["password_reset"]["endpoints"][0]["sources"]
    assert stages["mfa"]["observed"] is True
    assert stages["logout"]["observed"] is False

    assert flow["observed_stage_count"] == 3
    focus_blob = " ".join(flow["review_focus"])
    assert "password-reset flow is exposed" in focus_blob
    assert "MFA endpoints are present" in focus_blob
    assert "no logout" in focus_blob  # login seen, logout not


def test_flow_never_returns_a_stage_as_a_finding():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)
        db.add(HttpTransaction(
            project_id=project.id, method="POST", url="https://api.example.com/login",
        ))
        db.commit()
        flow = build_auth_flow(db, project.id)

    blob = repr(flow).lower()
    assert "vulnerable" not in blob
    assert "confirmed" not in blob
    assert "never exercises these" in flow["note"]
