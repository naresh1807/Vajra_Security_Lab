import asyncio
import hashlib
import json
import zipfile
import shutil
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base
from app.evidence.export import EvidenceBundleError, build_evidence_bundle, remove_bundle
from app.evidence.router import export_evidence_bundle
from app.evidence.verify import verify_evidence_bundle
from app.evidence.models import EvidenceAttachment
from app.evidence.service import save_attachment
from app.http.models import HttpTransaction
from app.investigations.models import Investigation, InvestigationSource
from app.projects.models import Project


def _fixture_data(db: Session) -> tuple[Project, Investigation]:
    project = Project(name="Example Program", target="example.com", allowed_domains=["example.com"])
    db.add(project)
    db.commit()
    transaction = HttpTransaction(
        project_id=project.id,
        identity_profile_name="Account A",
        identity_profile_key="stable-account-a",
        profile_header_names=["Authorization"],
        method="GET",
        url="https://api.example.com/orders/1",
        request_headers={"Authorization": "Bearer raw-request-secret"},
        request_body='{"token":"raw-body-secret"}',
        status_code=200,
        response_headers={"content-type": "application/json"},
        response_cookies=["session=raw-cookie-secret; HttpOnly"],
        response_body='{"token":"raw-response-secret","id":1}',
        response_body_truncated=False,
        response_size_bytes=38,
        technologies=[],
        interesting_indicators=[],
    )
    db.add(transaction)
    db.commit()
    investigation = Investigation(
        project_id=project.id,
        title="Potential order authorization boundary",
        target="api.example.com",
        endpoint="/orders/{id}",
        source=InvestigationSource.DIFF_RESULT,
        ai_notes="Different controlled identities returned comparable responses.",
        linked_transaction_ids=[transaction.id],
        access_control_snapshot={
            "schema_version": 1,
            "scenario_name": "Orders matrix",
            "warnings": [],
            "selected_cells": [{
                "transaction_a_id": transaction.id,
                "transaction_b_id": transaction.id + 1,
                "identity_a": "Account A",
                "identity_b": "Account B",
                "category": "Worth a closer look",
                "confidence": 50,
            }],
        },
    )
    db.add(investigation)
    db.commit()
    return project, investigation


@pytest.fixture
def export_temp_dir():
    path = Path(__file__).resolve().parent / ".runtime" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def export_db(export_temp_dir, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(export_temp_dir / "uploads"))
    monkeypatch.setattr(settings, "max_evidence_export_bytes", 10 * 1024 * 1024)
    monkeypatch.setattr(settings, "max_evidence_export_attachments", 10)
    db_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(db_engine)
    with Session(db_engine) as db:
        yield db


def test_bundle_contains_masked_evidence_manifest_screenshot_and_valid_checksums(export_db):
    db = export_db
    project, investigation = _fixture_data(db)
    save_attachment(
        db,
        project.id,
        investigation.id,
        "../../ownership proof.png",
        "image/png",
        b"safe-test-image-bytes",
        "Account B viewing Account A's order",
    )

    artifact = build_evidence_bundle(db, project, investigation)
    try:
        with zipfile.ZipFile(artifact.path) as archive:
            names = set(archive.namelist())
            assert "report.md" in names
            assert "manifest.json" in names
            assert "SHA256SUMS" in names
            assert "evidence/access_control_snapshot.json" in names
            assert f"evidence/transactions/{investigation.linked_transaction_ids[0]}.json" in names
            screenshot_name = next(name for name in names if name.startswith("screenshots/"))
            assert ".." not in screenshot_name
            assert archive.read(screenshot_name) == b"safe-test-image-bytes"

            transaction_data = archive.read(
                f"evidence/transactions/{investigation.linked_transaction_ids[0]}.json"
            ).decode()
            assert "raw-request-secret" not in transaction_data
            assert "raw-body-secret" not in transaction_data
            assert "raw-response-secret" not in transaction_data
            assert "raw-cookie-secret" not in transaction_data
            assert "Account A" in transaction_data

            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["masking"]["http_transactions_masked"] is True
            assert manifest["masking"]["screenshots_automatically_redacted"] is False
            assert manifest["screenshots"][0]["unredacted_user_upload"] is True
            assert manifest["screenshots"][0]["status"] == "included"

            checksum_entries = {}
            for line in archive.read("SHA256SUMS").decode().splitlines():
                digest, archive_path = line.split("  ", 1)
                checksum_entries[archive_path] = digest
            assert "manifest.json" in checksum_entries
            for archive_path, expected_digest in checksum_entries.items():
                assert hashlib.sha256(archive.read(archive_path)).hexdigest() == expected_digest
        with artifact.path.open("rb") as bundle_file:
            verification = verify_evidence_bundle(bundle_file, artifact.filename)
        assert verification.valid is True
        assert verification.project["id"] == project.id
        assert verification.investigation["id"] == investigation.id
    finally:
        remove_bundle(artifact.path)
    assert not artifact.path.exists()


def test_bundle_excludes_screenshot_outside_investigation_directory(export_db, export_temp_dir):
    db = export_db
    project, investigation = _fixture_data(db)
    outside = export_temp_dir / "outside.png"
    outside.write_bytes(b"must-not-be-exported")
    attachment = EvidenceAttachment(
        project_id=project.id,
        investigation_id=investigation.id,
        filename="outside.png",
        content_type="image/png",
        file_path=str(outside),
        size_bytes=outside.stat().st_size,
        caption="tampered path",
    )
    db.add(attachment)
    db.commit()

    artifact = build_evidence_bundle(db, project, investigation)
    try:
        with zipfile.ZipFile(artifact.path) as archive:
            assert not any(name.startswith("screenshots/") for name in archive.namelist())
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["screenshots"][0]["status"] == "rejected_unsafe_path"
            assert any("unsafe storage path" in warning for warning in manifest["warnings"])
    finally:
        remove_bundle(artifact.path)


def test_bundle_limit_failure_removes_temporary_zip(export_db, monkeypatch):
    db = export_db
    project, investigation = _fixture_data(db)
    monkeypatch.setattr(settings, "max_evidence_export_bytes", 10)
    export_directory = Path(settings.upload_dir) / ".exports"
    before = set(export_directory.glob("vajra-evidence-*.zip")) if export_directory.exists() else set()

    with pytest.raises(EvidenceBundleError, match="source limit"):
        build_evidence_bundle(db, project, investigation)

    after = set(export_directory.glob("vajra-evidence-*.zip")) if export_directory.exists() else set()
    assert after == before


def test_export_response_deletes_temporary_bundle_after_delivery(export_db):
    db = export_db
    project, investigation = _fixture_data(db)

    response = export_evidence_bundle(project.id, investigation.id, db)
    bundle_path = Path(response.path)
    assert bundle_path.is_file()
    assert response.media_type == "application/zip"
    assert response.background is not None

    asyncio.run(response.background())
    assert not bundle_path.exists()
