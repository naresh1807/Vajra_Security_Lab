"""
GET /api/health - the operational readiness report (docs/PRODUCTION.md
"Required operational checks"): queue, database + migration state, and
data-encryption key.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base, database_health
from app.core.encryption import encryption_health


def test_database_health_reports_migration_state_on_a_current_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    # A create_all() DB has no alembic_version row -> "behind", but reachable.
    monkeypatch.setattr("app.core.database.engine", engine)
    health = database_health()
    assert health["reachable"] is True
    assert health["migrations"] in {"behind", "up_to_date"}
    assert health["head_revision"]  # the scripts always have a head


def test_database_health_reports_an_unreachable_db(monkeypatch):
    bad = create_engine("sqlite:////this/path/does/not/exist/vajra.db")
    monkeypatch.setattr("app.core.database.engine", bad)
    health = database_health()
    assert health["reachable"] is False
    assert "error" in health


def test_encryption_health_ok_with_a_key(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setattr("app.core.encryption.settings.data_encryption_key", Fernet.generate_key().decode())
    import app.core.encryption as enc

    enc.get_fernet.cache_clear()
    health = encryption_health()
    enc.get_fernet.cache_clear()
    assert health == {"ready": True, "source": "env"}


def test_encryption_health_flags_a_broken_key(monkeypatch):
    monkeypatch.setattr("app.core.encryption.settings.data_encryption_key", "not-a-fernet-key")
    import app.core.encryption as enc

    enc.get_fernet.cache_clear()
    health = encryption_health()
    enc.get_fernet.cache_clear()
    assert health["ready"] is False


def test_health_endpoint_is_degraded_when_a_subsystem_is_down(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as main

    monkeypatch.setattr(main, "queue_health", lambda: {"available": False, "backend": "rq"})
    monkeypatch.setattr(main, "database_health", lambda: {"reachable": True, "migrations": "up_to_date"})
    monkeypatch.setattr(main, "encryption_health", lambda: {"ready": True, "source": "env"})

    body = TestClient(main.app).get("/api/health").json()
    assert body["status"] == "degraded"
    assert body["queue"]["available"] is False
