"""Authenticated encryption for sensitive values persisted by Vajra."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

PREFIX = "vajra:v1:"


def _key_path() -> Path:
    path = Path(settings.data_encryption_key_file).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path.resolve()


@lru_cache(maxsize=1)
def get_fernet() -> Fernet:
    configured = settings.data_encryption_key.strip()
    if configured:
        key = configured.encode("ascii")
    else:
        path = _key_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as handle:
                key = Fernet.generate_key()
                handle.write(key)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except FileExistsError:
            key = path.read_bytes().strip()
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("VAJRA_DATA_ENCRYPTION_KEY is not a valid Fernet key.") from exc


def encrypt_text(value: str) -> str:
    if value.startswith(PREFIX):
        return value
    return PREFIX + get_fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_text(value: str) -> str:
    if not value.startswith(PREFIX):
        return value  # backwards-compatible read of a legacy plaintext row
    try:
        return get_fernet().decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Encrypted database value cannot be decrypted with the configured Vajra key.") from exc


def encrypt_json(value: Any) -> str:
    return encrypt_text(json.dumps(value, separators=(",", ":"), ensure_ascii=False))


def decrypt_json(value: str) -> Any:
    return json.loads(decrypt_text(value))
