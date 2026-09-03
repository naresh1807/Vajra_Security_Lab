import asyncio
import hashlib
import io
import json
import stat
import zipfile

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

from app.core.config import settings
from app.evidence.verify import EvidenceVerificationLimitError, verify_evidence_bundle
from app.evidence.router import verify_uploaded_evidence_bundle


def _valid_bundle() -> bytes:
    payloads = {
        "report.md": b"# Verified test report\n",
        "evidence/transactions/1.json": b'{"id":1,"masking_verifiable":true}',
    }
    records = [
        {
            "path": path,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "category": "report" if path == "report.md" else "masked_http_transaction",
        }
        for path, data in payloads.items()
    ]
    manifest = {
        "schema_version": 1,
        "generated_at": "2026-09-02T00:00:00+00:00",
        "generator": "Vajra Security Lab",
        "project": {"id": 7, "name": "Example Program", "target": "example.com"},
        "investigation": {"id": 9, "title": "Authorization review", "status": "open", "confidence": 60},
        "masking": {
            "http_transactions_masked": True,
            "screenshots_automatically_redacted": False,
            "report_text_automatically_redacted": False,
        },
        "warnings": ["Review screenshots before sharing."],
        "screenshots": [],
        "files": records,
    }
    payloads["manifest.json"] = json.dumps(manifest).encode()
    sums = "\n".join(
        f"{hashlib.sha256(data).hexdigest()}  {path}" for path, data in payloads.items()
    ) + "\n"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in payloads.items():
            archive.writestr(path, data)
        archive.writestr("SHA256SUMS", sums.encode())
    return output.getvalue()


def _rewrite_bundle(original: bytes, replacements: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for info in source.infolist():
            target.writestr(info.filename, replacements.get(info.filename, source.read(info)))
    return output.getvalue()


def test_valid_bundle_passes_archive_manifest_and_checksum_verification():
    result = verify_evidence_bundle(io.BytesIO(_valid_bundle()), "evidence.zip")

    assert result.valid is True
    assert result.archive_safe is True
    assert result.manifest_valid is True
    assert result.checksums_valid is True
    assert result.project["name"] == "Example Program"
    assert all(item.checksum_status == "matched" for item in result.files if item.path != "SHA256SUMS")
    assert next(item for item in result.files if item.path == "SHA256SUMS").checksum_status == "not_applicable"


def test_altered_payload_is_reported_without_rendering_content():
    tampered = _rewrite_bundle(_valid_bundle(), {"report.md": b"altered evidence"})

    result = verify_evidence_bundle(io.BytesIO(tampered), "tampered.zip")

    assert result.valid is False
    assert result.archive_safe is True
    assert result.checksums_valid is False
    assert any("Checksum mismatch for 'report.md'" in error for error in result.errors)


def test_traversal_and_symlink_entries_are_rejected_without_extraction():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("../escape.txt", b"unsafe")
        symlink = zipfile.ZipInfo("screenshots/link.png")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(symlink, "../../outside")

    result = verify_evidence_bundle(io.BytesIO(output.getvalue()), "unsafe.zip")

    assert result.valid is False
    assert result.archive_safe is False
    assert any("Unsafe archive path" in error for error in result.errors)
    assert any("Symbolic links" in error for error in result.errors)


def test_case_colliding_duplicate_paths_are_rejected():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("Report.md", b"one")
        archive.writestr("report.md", b"two")

    result = verify_evidence_bundle(io.BytesIO(output.getvalue()), "duplicate.zip")

    assert result.archive_safe is False
    assert any("case-colliding" in error for error in result.errors)


def test_suspicious_compression_ratio_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "max_evidence_verify_compression_ratio", 2.0)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("large.txt", b"0" * (1024 * 1024))

    result = verify_evidence_bundle(io.BytesIO(output.getvalue()), "bomb.zip")

    assert result.archive_safe is False
    assert any("suspicious compression ratio" in error for error in result.errors)


def test_non_zip_and_oversized_uploads_fail_safely(monkeypatch):
    invalid = verify_evidence_bundle(io.BytesIO(b"not a zip"), "fake.zip")
    assert invalid.valid is False
    assert "not a readable ZIP" in invalid.errors[0]

    monkeypatch.setattr(settings, "max_evidence_verify_upload_bytes", 4)
    with pytest.raises(EvidenceVerificationLimitError, match="upload limit"):
        verify_evidence_bundle(io.BytesIO(_valid_bundle()), "too-large.zip")


def test_manifest_record_tampering_is_detected_even_with_matching_sha_index():
    original = _valid_bundle()
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    manifest["files"][0]["size_bytes"] = 999999
    modified_manifest = json.dumps(manifest).encode()

    # Rebuild SHA256SUMS so checksum validation passes; manifest semantics must still fail.
    intermediate = _rewrite_bundle(original, {"manifest.json": modified_manifest})
    with zipfile.ZipFile(io.BytesIO(intermediate)) as archive:
        checksum_payloads = {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if info.filename != "SHA256SUMS"
        }
    sums = "\n".join(
        f"{hashlib.sha256(data).hexdigest()}  {path}" for path, data in checksum_payloads.items()
    ) + "\n"
    tampered = _rewrite_bundle(intermediate, {"SHA256SUMS": sums.encode()})

    result = verify_evidence_bundle(io.BytesIO(tampered), "manifest-tampered.zip")

    assert result.checksums_valid is True
    assert result.manifest_valid is False
    assert any("Manifest size does not match" in error for error in result.errors)


def test_upload_endpoint_verifies_zip_and_closes_upload_handle():
    upload = UploadFile(
        io.BytesIO(_valid_bundle()),
        filename="evidence.zip",
        headers=Headers({"content-type": "application/zip"}),
    )

    result = asyncio.run(verify_uploaded_evidence_bundle(upload))

    assert result.valid is True
    assert upload.file.closed is True


def test_upload_endpoint_rejects_content_type_and_still_closes_handle():
    upload = UploadFile(
        io.BytesIO(_valid_bundle()),
        filename="evidence.txt",
        headers=Headers({"content-type": "text/plain"}),
    )

    with pytest.raises(HTTPException, match="ZIP files only"):
        asyncio.run(verify_uploaded_evidence_bundle(upload))
    assert upload.file.closed is True
