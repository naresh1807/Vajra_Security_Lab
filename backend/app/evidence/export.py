from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.evidence.service import build_evidence_package
from app.investigations.models import Investigation
from app.projects.models import Project
from app.reports.service import render_report_markdown, seed_report


class EvidenceBundleError(Exception):
    pass


@dataclass(frozen=True)
class EvidenceBundleArtifact:
    path: Path
    filename: str
    size_bytes: int


def remove_bundle(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_archive_name(filename: str, attachment_id: int) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).strip("._") or "screenshot"
    return f"screenshots/{attachment_id}_{cleaned[:120]}"


def build_evidence_bundle(db: Session, project: Project, investigation: Investigation) -> EvidenceBundleArtifact:
    package = build_evidence_package(db, investigation)
    if len(package.attachments) > settings.max_evidence_export_attachments:
        raise EvidenceBundleError(
            f"Evidence bundle has {len(package.attachments)} screenshots; the configured maximum is "
            f"{settings.max_evidence_export_attachments}."
        )

    report_fields: object = investigation.report
    if report_fields is None:
        report_fields = seed_report(investigation, package.transactions)

    export_directory = (Path(settings.upload_dir) / ".exports").resolve()
    export_directory.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp_path = tempfile.mkstemp(
        prefix="vajra-evidence-", suffix=".zip", dir=export_directory
    )
    os.close(descriptor)
    temp_path = Path(raw_temp_path)
    records: list[dict] = []
    screenshot_manifest: list[dict] = []
    warnings: list[str] = [
        "HTTP transaction fields are masked before export.",
        "User-authored report text and uploaded screenshots are exported as supplied and must be reviewed before sharing.",
    ]
    total_source_bytes = 0

    def add_bytes(archive: zipfile.ZipFile, archive_path: str, data: bytes, category: str) -> None:
        nonlocal total_source_bytes
        total_source_bytes += len(data)
        if total_source_bytes > settings.max_evidence_export_bytes:
            raise EvidenceBundleError(
                f"Evidence bundle exceeds the configured {settings.max_evidence_export_bytes}-byte source limit."
            )
        archive.writestr(archive_path, data)
        records.append({
            "path": archive_path,
            "sha256": _sha256_bytes(data),
            "size_bytes": len(data),
            "category": category,
        })

    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            add_bytes(
                archive,
                "report.md",
                render_report_markdown(investigation, report_fields).encode("utf-8"),
                "report",
            )
            for transaction in package.transactions:
                transaction_json = json.dumps(
                    transaction.model_dump(mode="json"), indent=2, ensure_ascii=False
                ).encode("utf-8")
                add_bytes(
                    archive,
                    f"evidence/transactions/{transaction.id}.json",
                    transaction_json,
                    "masked_http_transaction",
                )
                if not transaction.masking_verifiable:
                    warnings.append(
                        f"Transaction #{transaction.id} contains a non-JSON body; body masking is best effort and requires review."
                    )

            if package.access_control_snapshot:
                snapshot_json = json.dumps(
                    package.access_control_snapshot, indent=2, ensure_ascii=False
                ).encode("utf-8")
                add_bytes(
                    archive,
                    "evidence/access_control_snapshot.json",
                    snapshot_json,
                    "access_control_snapshot",
                )

            expected_directory = (
                Path(settings.upload_dir) / str(project.id) / str(investigation.id)
            ).resolve()
            attachments_by_id = {attachment.id: attachment for attachment in investigation.evidence_attachments}
            for attachment_out in package.attachments:
                attachment = attachments_by_id.get(attachment_out.id)
                unbaked = list(attachment.annotations or []) if attachment is not None else []
                entry = {
                    "attachment_id": attachment_out.id,
                    "original_filename": attachment_out.filename,
                    "caption": attachment_out.caption,
                    "content_type": attachment_out.content_type,
                    "declared_size_bytes": attachment_out.size_bytes,
                    "unredacted_user_upload": True,
                    "has_unbaked_annotations": bool(unbaked),
                    "annotations": unbaked,
                }
                if unbaked:
                    redactions = sum(1 for shape in unbaked if shape.get("type") == "redact")
                    warnings.append(
                        f"Screenshot attachment #{attachment_out.id} has {len(unbaked)} annotation(s)"
                        + (f" including {redactions} redaction box(es)" if redactions else "")
                        + " that are NOT baked into the exported image file. Use 'Flatten & replace' before "
                        "sharing, or treat the raw image as unredacted."
                    )
                if attachment is None:
                    entry["status"] = "missing_database_record"
                    screenshot_manifest.append(entry)
                    warnings.append(f"Screenshot attachment #{attachment_out.id} could not be exported.")
                    continue
                source = Path(attachment.file_path).resolve()
                try:
                    source.relative_to(expected_directory)
                except ValueError:
                    entry["status"] = "rejected_unsafe_path"
                    screenshot_manifest.append(entry)
                    warnings.append(f"Screenshot attachment #{attachment.id} had an unsafe storage path and was excluded.")
                    continue
                if not source.is_file():
                    entry["status"] = "missing_file"
                    screenshot_manifest.append(entry)
                    warnings.append(f"Screenshot attachment #{attachment.id} is missing from storage.")
                    continue
                actual_size = source.stat().st_size
                total_source_bytes += actual_size
                if total_source_bytes > settings.max_evidence_export_bytes:
                    raise EvidenceBundleError(
                        f"Evidence bundle exceeds the configured {settings.max_evidence_export_bytes}-byte source limit."
                    )
                archive_path = _safe_archive_name(attachment.filename, attachment.id)
                checksum = _sha256_file(source)
                archive.write(source, archive_path)
                records.append({
                    "path": archive_path,
                    "sha256": checksum,
                    "size_bytes": actual_size,
                    "category": "unredacted_user_screenshot",
                })
                entry.update({
                    "status": "included",
                    "archive_path": archive_path,
                    "actual_size_bytes": actual_size,
                    "sha256": checksum,
                })
                screenshot_manifest.append(entry)

            manifest = {
                "schema_version": 1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "generator": settings.app_name,
                "project": {"id": project.id, "name": project.name, "target": project.target},
                "investigation": {
                    "id": investigation.id,
                    "title": investigation.title,
                    "status": investigation.status.value,
                    "confidence": investigation.confidence,
                },
                "masking": {
                    "http_transactions_masked": True,
                    "screenshots_automatically_redacted": False,
                    "report_text_automatically_redacted": False,
                },
                "warnings": warnings,
                "screenshots": screenshot_manifest,
                "files": list(records),
                "integrity": "SHA256SUMS verifies every payload file and manifest.json; it does not list itself.",
            }
            manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
            add_bytes(archive, "manifest.json", manifest_bytes, "manifest")
            checksum_lines = [f"{record['sha256']}  {record['path']}" for record in records]
            add_bytes(
                archive,
                "SHA256SUMS",
                ("\n".join(checksum_lines) + "\n").encode("utf-8"),
                "checksum_index",
            )
    except Exception:
        remove_bundle(temp_path)
        raise

    return EvidenceBundleArtifact(
        path=temp_path,
        filename=f"vajra-investigation-{investigation.id}-evidence.zip",
        size_bytes=temp_path.stat().st_size,
    )
