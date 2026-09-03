from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.encryption import PREFIX, get_fernet
from app.http.models import HttpTransaction
from app.http.router import _transaction_out
from app.identities.models import IdentityProfile
from app.identities.service import merge_profile_headers, profile_out, validate_secret_headers


def test_identity_headers_are_strictly_validated():
    assert validate_secret_headers({"Authorization": "Bearer token"}) == {"Authorization": "Bearer token"}
    with pytest.raises(HTTPException, match="cannot control"):
        validate_secret_headers({"Host": "evil.example"})
    with pytest.raises(HTTPException, match="invalid value"):
        validate_secret_headers({"X-API-Key": "secret\r\nInjected: yes"})
    with pytest.raises(HTTPException, match="Duplicate"):
        validate_secret_headers({"Authorization": "one", "authorization": "two"})


def test_profile_wins_case_insensitive_header_merge():
    merged = merge_profile_headers(
        {"authorization": "manual", "Accept": "application/json"},
        {"Authorization": "stored", "X-API-Key": "secret"},
    )
    assert merged == {"Accept": "application/json", "Authorization": "stored", "X-API-Key": "secret"}


def test_profile_api_shape_never_contains_secret_values():
    now = datetime.now(timezone.utc)
    profile = IdentityProfile(
        id=1,
        project_id=4,
        name="Account A",
        description="standard user",
        secret_headers={"Authorization": "Bearer do-not-return", "X-API-Key": "also-secret"},
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    output = profile_out(profile).model_dump()
    serialized = str(output)
    assert output["header_names"] == ["Authorization", "X-API-Key"]
    assert "do-not-return" not in serialized
    assert "also-secret" not in serialized


def test_identity_headers_are_encrypted_at_rest(monkeypatch):
    from app.core import encryption

    monkeypatch.setattr(encryption.settings, "data_encryption_key", Fernet.generate_key().decode())
    get_fernet.cache_clear()
    db_engine = create_engine("sqlite:///:memory:")
    IdentityProfile.__table__.create(db_engine)

    with Session(db_engine) as db:
        profile = IdentityProfile(
            project_id=1,
            name="Account A",
            secret_headers={"Authorization": "Bearer raw-secret"},
        )
        db.add(profile)
        db.commit()
        profile_id = profile.id

    with db_engine.connect() as connection:
        raw = connection.execute(
            text("SELECT secret_headers FROM identity_profiles WHERE id=:id"), {"id": profile_id}
        ).scalar_one()
        assert raw.startswith(PREFIX)
        assert "raw-secret" not in raw

    with Session(db_engine) as db:
        assert db.get(IdentityProfile, profile_id).secret_headers == {"Authorization": "Bearer raw-secret"}
    get_fernet.cache_clear()


def test_transaction_serializer_masks_profile_headers_only():
    tx = HttpTransaction(
        id=1,
        project_id=1,
        identity_profile_id=3,
        identity_profile_name="Account A",
        profile_header_names=["Authorization", "X-API-Key"],
        method="GET",
        url="https://example.com/me",
        request_headers={"authorization": "Bearer hidden", "X-API-Key": "hidden-too", "Accept": "application/json"},
        request_body=None,
        status_code=200,
        response_headers={},
        response_cookies=[],
        response_body="ok",
        response_body_truncated=False,
        response_size_bytes=2,
        timing_ms=1.0,
        technologies=[],
        interesting_indicators=[],
        error=None,
        created_at=datetime.now(timezone.utc),
    )

    output = _transaction_out(tx)

    assert output.request_headers["authorization"] == "[STORED IDENTITY SECRET]"
    assert output.request_headers["X-API-Key"] == "[STORED IDENTITY SECRET]"
    assert output.request_headers["Accept"] == "application/json"


def test_pre_alembic_bridge_adds_identity_attribution_columns(monkeypatch):
    from app.core import database

    legacy_engine = create_engine("sqlite:///:memory:")
    with legacy_engine.begin() as connection:
        connection.execute(text("CREATE TABLE identity_profiles (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE http_transactions (id INTEGER PRIMARY KEY)"))
    monkeypatch.setattr(database, "engine", legacy_engine)

    database._add_legacy_identity_profile_columns()

    with legacy_engine.connect() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(http_transactions)"))}
        indexes = {row[1] for row in connection.execute(text("PRAGMA index_list(http_transactions)"))}
    assert {
        "identity_profile_id", "identity_profile_key", "identity_profile_name", "profile_header_names"
    }.issubset(columns)
    assert "ix_http_transactions_identity_profile_id" in indexes
