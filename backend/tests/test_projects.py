"""
Project CRUD, focused on Hunt Mode being a real, switchable setting.

The frontend Copilot panel changes how much it volunteers based on
`project.mode`, and it flips the mode through `PATCH /api/projects/{id}`,
so these tests pin that endpoint's contract: it accepts a valid mode,
persists it, and rejects anything that isn't one of the three.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.projects.models import HuntMode, Project
from app.projects.router import router as projects_router
from app.recon.service import recon_source_enabled


def _client_and_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(projects_router)
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), Session


def _seed_project(Session, **overrides) -> int:
    with Session() as db:
        project = Project(name="Example Program", target="example.com", **overrides)
        db.add(project)
        db.commit()
        return project.id


def test_new_project_defaults_to_guided_mode():
    _, Session = _client_and_session()
    project_id = _seed_project(Session)
    with Session() as db:
        assert db.get(Project, project_id).mode == HuntMode.GUIDED


def test_patch_switches_hunt_mode_and_persists_it():
    client, Session = _client_and_session()
    project_id = _seed_project(Session)

    res = client.patch(f"/api/projects/{project_id}", json={"mode": "advanced"})
    assert res.status_code == 200
    assert res.json()["mode"] == "advanced"

    # GET reflects it, and so does the row itself.
    assert client.get(f"/api/projects/{project_id}").json()["mode"] == "advanced"
    with Session() as db:
        assert db.get(Project, project_id).mode == HuntMode.ADVANCED


def test_patch_rejects_an_unknown_hunt_mode():
    client, Session = _client_and_session()
    project_id = _seed_project(Session)

    res = client.patch(f"/api/projects/{project_id}", json={"mode": "expert"})
    assert res.status_code == 422
    with Session() as db:
        assert db.get(Project, project_id).mode == HuntMode.GUIDED


def test_patch_leaves_other_fields_untouched():
    client, Session = _client_and_session()
    project_id = _seed_project(Session, rate_limit_rps=3.0)

    client.patch(f"/api/projects/{project_id}", json={"mode": "standard"})
    with Session() as db:
        project = db.get(Project, project_id)
        assert project.mode == HuntMode.STANDARD
        assert project.rate_limit_rps == 3.0
        assert project.target == "example.com"


def test_patch_persists_recon_source_switches_and_rejects_unknown_keys():
    client, Session = _client_and_session()
    project_id = _seed_project(Session)

    ok = client.patch(f"/api/projects/{project_id}", json={"recon_sources": {"wayback": False, "katana": True}})
    assert ok.status_code == 200
    assert ok.json()["recon_sources"] == {"wayback": False, "katana": True}

    bad = client.patch(f"/api/projects/{project_id}", json={"recon_sources": {"nmap": True}})
    assert bad.status_code == 422


def test_recon_source_enabled_respects_project_switch_and_deployment(monkeypatch):
    _, Session = _client_and_session()
    project_id = _seed_project(Session, recon_sources={"subfinder": False})
    with Session() as db:
        project = db.get(Project, project_id)

        # Project turned subfinder off - even though the deployment allows it.
        monkeypatch.setattr("app.recon.service.settings.subfinder_enabled", True)
        assert recon_source_enabled(project, "subfinder") is False

        # A project can't force on a source the deployment disabled.
        project.recon_sources = {"wayback": True}
        monkeypatch.setattr("app.recon.service.settings.wayback_enabled", False)
        assert recon_source_enabled(project, "wayback") is False

        # Default (key absent) = on.
        project.recon_sources = {}
        monkeypatch.setattr("app.recon.service.settings.wayback_enabled", True)
        assert recon_source_enabled(project, "wayback") is True
