"""
Vajra Access Control Workbench (Section 17).

The workbench is a planning layer over Vajra Diff: for each endpoint
shape it says whether a comparison is ready to run or what to capture
next, and never runs anything itself.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.http.models import HttpTransaction
from app.identities.models import IdentityProfile
from app.projects.models import Project
from app.workbench.service import build_workbench


def _project(db: Session) -> Project:
    project = Project(
        name="Workbench", target="example.com", allowed_domains=["example.com"],
        allowed_subdomains=[], excluded_assets=[], rate_limit_rps=1.0,
    )
    db.add(project)
    db.flush()
    return project


def _tx(project_id: int, url: str, *, key: str | None, name: str | None, method: str = "GET", status: int | None = 200):
    return HttpTransaction(
        project_id=project_id, method=method, url=url, status_code=status,
        identity_profile_key=key, identity_profile_name=name,
    )


def test_workbench_always_ships_the_four_test_types():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)
        db.commit()
        wb = build_workbench(db, project.id)

    assert [t["key"] for t in wb["test_types"]] == ["horizontal", "vertical", "object_ownership", "role_boundary"]
    assert all(t["how_to_set_up"] and t["evidence_needed"] for t in wb["test_types"])
    assert wb["endpoint_groups"] == []
    assert any("two controlled identities" in w for w in wb["setup_warnings"])
    assert any("No requests captured" in w for w in wb["setup_warnings"])


def test_two_identities_on_one_shape_is_ready_with_a_suggested_pair():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)
        db.add(IdentityProfile(project_id=project.id, name="Alice", secret_headers={"Authorization": "a"}, enabled=True))
        db.add(IdentityProfile(project_id=project.id, name="Bob", secret_headers={"Authorization": "b"}, enabled=True))
        db.add(_tx(project.id, "https://api.example.com/api/orders/1", key="alice", name="Alice"))
        db.add(_tx(project.id, "https://api.example.com/api/orders/2", key="bob", name="Bob"))
        db.commit()
        wb = build_workbench(db, project.id)

    assert wb["ready_endpoint_count"] == 1
    group = wb["endpoint_groups"][0]
    assert group["pattern"] == "/api/orders/{id}"
    assert group["readiness"] == "ready"
    assert group["distinct_identities"] == 2
    assert group["distinct_object_identifiers"] == 2
    assert len(group["suggested_pairs"]) == 1
    pair = group["suggested_pairs"][0]
    assert {pair["identity_a"], pair["identity_b"]} == {"Alice", "Bob"}
    assert wb["setup_warnings"] == []  # two enabled identities, captures present


def test_same_identity_twice_needs_a_second_identity():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)
        db.add(_tx(project.id, "https://api.example.com/api/orders/1", key="alice", name="Alice"))
        db.add(_tx(project.id, "https://api.example.com/api/orders/2", key="alice", name="Alice"))
        db.commit()
        wb = build_workbench(db, project.id)

    group = wb["endpoint_groups"][0]
    assert group["readiness"] == "needs_second_identity"
    assert group["suggested_pairs"] == []
    assert "Alice" in group["next_step"]


def test_ready_but_same_object_id_warns_about_the_horizontal_setup():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)
        db.add(_tx(project.id, "https://api.example.com/api/orders/1", key="alice", name="Alice"))
        db.add(_tx(project.id, "https://api.example.com/api/orders/1", key="bob", name="Bob"))
        db.commit()
        wb = build_workbench(db, project.id)

    group = wb["endpoint_groups"][0]
    assert group["readiness"] == "ready"
    assert group["distinct_object_identifiers"] == 1
    assert "object owned by the other" in group["next_step"]


def test_workbench_never_sends_and_says_so():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)
        db.commit()
        wb = build_workbench(db, project.id)

    assert "never sends these comparisons for you" in wb["note"]
    assert "confirmed" not in wb["note"].lower()
