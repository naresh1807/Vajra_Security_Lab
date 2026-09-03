from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import PurePosixPath
from typing import BinaryIO

from app.core.config import settings
from app.evidence.schemas import EvidenceBundleVerificationOut, VerifiedBundleFileOut

_CHECKSUM_LINE = re.compile(r"^([0-9a-fA-F]{64})  (.+)$")
_ALLOWED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
_TEXT_METADATA_LIMIT = 2 * 1024 * 1024
_MAX_ARCHIVE_PATH_CHARS = 512


class EvidenceVerificationLimitError(Exception):
    pass


def _safe_member_path(name: str) -> bool:
    if not name or len(name) > _MAX_ARCHIVE_PATH_CHARS or "\x00" in name or "\\" in name or name.startswith(("/", "~")):
        return False
    if re.match(r"^[A-Za-z]:", name):
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK


def _path_label(name: str) -> str:
    return repr(name if len(name) <= 240 else name[:237] + "...")


def _base_result(filename: str, compressed_size: int, error: str) -> EvidenceBundleVerificationOut:
    return EvidenceBundleVerificationOut(
        filename=filename,
        valid=False,
        archive_safe=False,
        manifest_valid=False,
        checksums_valid=False,
        compressed_size_bytes=compressed_size,
        uncompressed_size_bytes=0,
        file_count=0,
        files=[],
        warnings=[],
        errors=[error],
    )


def verify_evidence_bundle(fileobj: BinaryIO, filename: str) -> EvidenceBundleVerificationOut:
    fileobj.seek(0, 2)
    compressed_size = fileobj.tell()
    fileobj.seek(0)
    if compressed_size > settings.max_evidence_verify_upload_bytes:
        raise EvidenceVerificationLimitError(
            f"Bundle is {compressed_size} bytes; the upload limit is {settings.max_evidence_verify_upload_bytes} bytes."
        )
    if compressed_size == 0:
        return _base_result(filename, 0, "The uploaded bundle is empty.")

    try:
        archive = zipfile.ZipFile(fileobj)
    except (zipfile.BadZipFile, OSError):
        return _base_result(filename, compressed_size, "The uploaded file is not a readable ZIP archive.")

    with archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        errors: list[str] = []
        warnings: list[str] = [
            "Checksum validity proves internal consistency, not who created the bundle; Vajra bundles are not digitally signed."
        ]
        archive_safe = True
        if len(infos) > settings.max_evidence_verify_entries:
            errors.append(
                f"Archive contains {len(infos)} files; the safety limit is {settings.max_evidence_verify_entries}."
            )
            archive_safe = False

        declared_total = sum(info.file_size for info in infos)
        if declared_total > settings.max_evidence_verify_uncompressed_bytes:
            errors.append(
                f"Archive declares {declared_total} uncompressed bytes; the safety limit is "
                f"{settings.max_evidence_verify_uncompressed_bytes}."
            )
            archive_safe = False

        seen_names: set[str] = set()
        safe_by_name: dict[str, bool] = {}
        for info in infos:
            safe = _safe_member_path(info.filename)
            canonical = info.filename.casefold()
            if canonical in seen_names:
                errors.append(f"Duplicate or case-colliding archive path: {_path_label(info.filename)}.")
                safe = False
            seen_names.add(canonical)
            if not safe:
                errors.append(f"Unsafe archive path: {_path_label(info.filename)}.")
            if _is_symlink(info):
                errors.append(f"Symbolic links are not permitted in evidence bundles: {_path_label(info.filename)}.")
                safe = False
            if info.flag_bits & 0x1:
                errors.append(f"Encrypted ZIP entries are not supported: {_path_label(info.filename)}.")
                safe = False
            if info.compress_type not in _ALLOWED_COMPRESSION:
                errors.append(f"Unsupported compression method for {_path_label(info.filename)}.")
                safe = False
            if info.file_size > settings.max_evidence_verify_file_bytes:
                errors.append(
                    f"File {_path_label(info.filename)} exceeds the {settings.max_evidence_verify_file_bytes}-byte per-file limit."
                )
                safe = False
            ratio = info.file_size / max(info.compress_size, 1)
            if info.file_size >= 1024 * 1024 and ratio > settings.max_evidence_verify_compression_ratio:
                errors.append(
                    f"File {_path_label(info.filename)} has a suspicious compression ratio ({ratio:.1f}:1)."
                )
                safe = False
            safe_by_name[info.filename] = safe
            archive_safe = archive_safe and safe

        actual_hashes: dict[str, str] = {}
        actual_sizes: dict[str, int] = {}
        metadata_content: dict[str, bytes] = {}
        actual_total = 0
        if archive_safe:
            for info in infos:
                digest = hashlib.sha256()
                size = 0
                capture = info.filename in {"manifest.json", "SHA256SUMS"}
                captured = bytearray()
                try:
                    with archive.open(info, "r") as member:
                        while chunk := member.read(1024 * 1024):
                            size += len(chunk)
                            actual_total += len(chunk)
                            if size > settings.max_evidence_verify_file_bytes:
                                raise EvidenceVerificationLimitError(
                                    f"File {_path_label(info.filename)} expanded beyond the per-file safety limit."
                                )
                            if actual_total > settings.max_evidence_verify_uncompressed_bytes:
                                raise EvidenceVerificationLimitError(
                                    "Archive expanded beyond the total uncompressed safety limit."
                                )
                            digest.update(chunk)
                            if capture and len(captured) <= _TEXT_METADATA_LIMIT:
                                captured.extend(chunk)
                    actual_hashes[info.filename] = digest.hexdigest()
                    actual_sizes[info.filename] = size
                    if capture:
                        if len(captured) > _TEXT_METADATA_LIMIT:
                            errors.append(f"Metadata file {_path_label(info.filename)} exceeds {_TEXT_METADATA_LIMIT} bytes.")
                        else:
                            metadata_content[info.filename] = bytes(captured)
                except (RuntimeError, zipfile.BadZipFile, EvidenceVerificationLimitError) as exc:
                    errors.append(f"Could not safely read {_path_label(info.filename)}: {exc}")
                    archive_safe = False
                    break

        checksum_errors: list[str] = []
        expected_checksums: dict[str, str] = {}
        checksum_bytes = metadata_content.get("SHA256SUMS")
        if checksum_bytes is None:
            checksum_errors.append("SHA256SUMS is missing or unreadable.")
        else:
            try:
                checksum_text = checksum_bytes.decode("utf-8")
            except UnicodeDecodeError:
                checksum_errors.append("SHA256SUMS is not valid UTF-8 text.")
            else:
                for line_number, line in enumerate(checksum_text.splitlines(), start=1):
                    match = _CHECKSUM_LINE.fullmatch(line)
                    if not match:
                        checksum_errors.append(f"Malformed SHA256SUMS line {line_number}.")
                        continue
                    digest, path = match.groups()
                    if path in expected_checksums:
                        checksum_errors.append(f"SHA256SUMS lists {path!r} more than once.")
                    expected_checksums[path] = digest.lower()

        payload_paths = {info.filename for info in infos if info.filename != "SHA256SUMS"}
        for path in sorted(payload_paths - set(expected_checksums)):
            checksum_errors.append(f"No checksum is provided for {path!r}.")
        for path in sorted(set(expected_checksums) - payload_paths):
            checksum_errors.append(f"SHA256SUMS references a missing or forbidden file: {path!r}.")
        for path in sorted(payload_paths & set(expected_checksums)):
            if actual_hashes.get(path) != expected_checksums[path]:
                checksum_errors.append(f"Checksum mismatch for {path!r}.")
        checksums_valid = archive_safe and not checksum_errors
        errors.extend(checksum_errors)

        manifest_errors: list[str] = []
        manifest: dict | None = None
        manifest_bytes = metadata_content.get("manifest.json")
        if manifest_bytes is None:
            manifest_errors.append("manifest.json is missing or unreadable.")
        else:
            try:
                parsed = json.loads(manifest_bytes)
            except (UnicodeDecodeError, json.JSONDecodeError):
                manifest_errors.append("manifest.json is not valid UTF-8 JSON.")
            else:
                if not isinstance(parsed, dict):
                    manifest_errors.append("manifest.json must contain a JSON object.")
                else:
                    manifest = parsed
                    if manifest.get("schema_version") != 1:
                        manifest_errors.append("Unsupported or missing manifest schema_version.")
                    for key in (
                        "generated_at", "generator", "project", "investigation", "masking",
                        "files", "screenshots", "warnings",
                    ):
                        if key not in manifest:
                            manifest_errors.append(f"manifest.json is missing {key!r}.")
                    if not isinstance(manifest.get("generated_at"), str) or not manifest.get("generated_at"):
                        manifest_errors.append("Manifest generated_at must be a non-empty string.")
                    if not isinstance(manifest.get("generator"), str) or not manifest.get("generator"):
                        manifest_errors.append("Manifest generator must be a non-empty string.")
                    if not isinstance(manifest.get("project"), dict):
                        manifest_errors.append("Manifest project must be an object.")
                    if not isinstance(manifest.get("investigation"), dict):
                        manifest_errors.append("Manifest investigation must be an object.")
                    if not isinstance(manifest.get("screenshots"), list):
                        manifest_errors.append("Manifest screenshots must be a list.")
                    if not isinstance(manifest.get("warnings"), list):
                        manifest_errors.append("Manifest warnings must be a list.")
                    if not isinstance(manifest.get("files"), list):
                        manifest_errors.append("manifest files must be a list.")
                    else:
                        manifest_paths: set[str] = set()
                        for index, record in enumerate(manifest["files"]):
                            if not isinstance(record, dict):
                                manifest_errors.append(f"Manifest file record {index} is not an object.")
                                continue
                            path = record.get("path")
                            if not isinstance(path, str) or path in manifest_paths:
                                manifest_errors.append(f"Manifest file record {index} has an invalid or duplicate path.")
                                continue
                            manifest_paths.add(path)
                            if path not in actual_hashes:
                                manifest_errors.append(f"Manifest references missing file {path!r}.")
                                continue
                            if record.get("sha256") != actual_hashes[path]:
                                manifest_errors.append(f"Manifest checksum does not match {path!r}.")
                            if record.get("size_bytes") != actual_sizes[path]:
                                manifest_errors.append(f"Manifest size does not match {path!r}.")
                            if not isinstance(record.get("category"), str) or not record.get("category"):
                                manifest_errors.append(f"Manifest category is invalid for {path!r}.")
                        expected_manifest_paths = payload_paths - {"manifest.json"}
                        if manifest_paths != expected_manifest_paths:
                            missing = sorted(expected_manifest_paths - manifest_paths)
                            extra = sorted(manifest_paths - expected_manifest_paths)
                            if missing:
                                manifest_errors.append(f"Manifest omits payload files: {', '.join(missing)}.")
                            if extra:
                                manifest_errors.append(f"Manifest lists unexpected files: {', '.join(extra)}.")
                    masking = manifest.get("masking")
                    if not isinstance(masking, dict) or masking.get("http_transactions_masked") is not True:
                        manifest_errors.append("Manifest does not assert masked HTTP transactions.")
                    for warning in (
                        manifest.get("warnings", []) if isinstance(manifest.get("warnings"), list) else []
                    ):
                        if isinstance(warning, str) and warning not in warnings:
                            warnings.append(warning)
        manifest_valid = archive_safe and not manifest_errors
        errors.extend(manifest_errors)

        category_by_path = {}
        if manifest and isinstance(manifest.get("files"), list):
            category_by_path = {
                record.get("path"): record.get("category")
                for record in manifest["files"]
                if isinstance(record, dict) and isinstance(record.get("path"), str)
            }
        files = [
            VerifiedBundleFileOut(
                path=info.filename if len(info.filename) <= _MAX_ARCHIVE_PATH_CHARS else info.filename[:509] + "...",
                size_bytes=actual_sizes.get(info.filename, info.file_size),
                compressed_size_bytes=info.compress_size,
                category=category_by_path.get(info.filename),
                safe_path=safe_by_name.get(info.filename, False),
                checksum_status=(
                    "not_applicable"
                    if info.filename == "SHA256SUMS"
                    else "matched"
                    if actual_hashes.get(info.filename) == expected_checksums.get(info.filename)
                    else "not_listed" if info.filename not in expected_checksums
                    else "mismatch"
                ),
            )
            for info in infos
        ]
        return EvidenceBundleVerificationOut(
            filename=filename,
            valid=archive_safe and checksums_valid and manifest_valid and not errors,
            archive_safe=archive_safe,
            manifest_valid=manifest_valid,
            checksums_valid=checksums_valid,
            compressed_size_bytes=compressed_size,
            uncompressed_size_bytes=actual_total if actual_total else declared_total,
            file_count=len(infos),
            project=manifest.get("project") if manifest and isinstance(manifest.get("project"), dict) else None,
            investigation=(
                manifest.get("investigation")
                if manifest and isinstance(manifest.get("investigation"), dict)
                else None
            ),
            masking=manifest.get("masking") if manifest and isinstance(manifest.get("masking"), dict) else None,
            files=files,
            warnings=warnings,
            errors=errors,
        )
