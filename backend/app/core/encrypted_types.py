"""SQLAlchemy types that encrypt on write and decrypt on read."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import JSON, Text
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from app.core.encryption import decrypt_json, decrypt_text, encrypt_json, encrypt_text


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        return None if value is None else encrypt_text(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        return None if value is None else decrypt_text(value)


class EncryptedJSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        return None if value is None else encrypt_json(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        try:
            return decrypt_json(value)
        except json.JSONDecodeError:
            # Some legacy drivers may already have decoded a JSON scalar.
            return value


def compare_encrypted_type(
    context: Any,
    inspected_column: Any,
    metadata_column: Any,
    inspected_type: Any,
    metadata_type: Any,
) -> bool | None:
    """Treat legacy SQLite storage types as equivalent for encrypted columns.

    Older Vajra databases declared encrypted JSON values as SQLite ``JSON``;
    current databases use ``TEXT`` because ciphertext is an opaque string. Both
    have safely stored the same encrypted payloads, and rebuilding the table
    would not improve or migrate the data.
    """
    if context.dialect.name != "sqlite":
        return None
    if isinstance(metadata_type, EncryptedJSON) and isinstance(inspected_type, (JSON, Text)):
        return False
    if isinstance(metadata_type, EncryptedText) and isinstance(inspected_type, Text):
        return False
    return None
