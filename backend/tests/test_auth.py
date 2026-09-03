from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.middleware import AuthenticationMiddleware
from app.auth.models import User, UserSession
from app.auth.router import router as auth_router
from app.auth.security import hash_password, new_token, token_hash, verify_password
from app.core.database import Base, get_db
from app.projects.models import Project


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")
    assert first != second
    assert "correct horse" not in first
    assert verify_password("correct horse battery staple", first)
    assert not verify_password("wrong password", first)


def _secured_app(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr("app.auth.middleware.SessionLocal", Session)
    app = FastAPI()
    app.add_middleware(AuthenticationMiddleware)

    @app.get("/api/ping")
    def ping(request: Request):
        return {"user_id": request.state.user_id}

    @app.post("/api/change")
    def change():
        return {"changed": True}

    @app.get("/api/projects/{project_id}/ping")
    def project_ping(project_id: int):
        return {"project_id": project_id}

    return app, Session


def _create_user_session(Session, email: str):
    raw, csrf = new_token(), new_token()
    with Session() as db:
        user = User(email=email, password_hash=hash_password("long-enough-password"))
        db.add(user); db.flush()
        db.add(UserSession(
            user_id=user.id, token_hash=token_hash(raw), csrf_token=csrf,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db.commit()
        return user.id, raw, csrf


def test_protected_api_requires_session(monkeypatch):
    app, _ = _secured_app(monkeypatch)
    assert TestClient(app).get("/api/ping").status_code == 401


def test_mutation_requires_matching_csrf_cookie_and_header(monkeypatch):
    app, Session = _secured_app(monkeypatch)
    _, raw, csrf = _create_user_session(Session, "hunter@example.com")
    client = TestClient(app)
    client.cookies.set("vajra_session", raw)
    client.cookies.set("vajra_csrf", csrf)
    assert client.get("/api/ping").status_code == 200
    assert client.post("/api/change").status_code == 403
    assert client.post("/api/change", headers={"X-CSRF-Token": csrf}).status_code == 200


def test_project_owner_cannot_access_another_users_project(monkeypatch):
    app, Session = _secured_app(monkeypatch)
    owner_id, _, _ = _create_user_session(Session, "owner@example.com")
    _, intruder_raw, intruder_csrf = _create_user_session(Session, "intruder@example.com")
    with Session() as db:
        project = Project(
            owner_id=owner_id, name="Private", target="example.com", allowed_domains=["example.com"],
            allowed_subdomains=[], excluded_assets=[], rate_limit_rps=1.0,
        )
        db.add(project); db.commit(); project_id = project.id
    client = TestClient(app)
    client.cookies.set("vajra_session", intruder_raw)
    client.cookies.set("vajra_csrf", intruder_csrf)
    assert client.get(f"/api/projects/{project_id}/ping").status_code == 404


def test_repeated_failed_logins_are_throttled(monkeypatch):
    app, Session = _secured_app(monkeypatch)
    app.include_router(auth_router)
    def override_db():
        with Session() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    with Session() as db:
        db.add(User(email="rate@example.com", password_hash=hash_password("correct-password-long")))
        db.commit()
    client = TestClient(app)
    payload = {"email": "rate@example.com", "password": "incorrect-password"}
    for _ in range(5):
        assert client.post("/api/auth/login", json=payload).status_code == 401
    assert client.post("/api/auth/login", json=payload).status_code == 429
