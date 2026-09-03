from types import SimpleNamespace

from cryptography.fernet import Fernet
from sqlalchemy import JSON, Integer, Text, create_engine, text
from sqlalchemy.orm import Session

from app.core.encrypted_types import EncryptedJSON, EncryptedText, compare_encrypted_type
from app.core.encryption import PREFIX, decrypt_text, encrypt_text, get_fernet
from app.http.models import HttpTransaction


def test_encryption_round_trip_uses_versioned_ciphertext(monkeypatch):
    from app.core import encryption

    monkeypatch.setattr(encryption.settings, "data_encryption_key", Fernet.generate_key().decode())
    get_fernet.cache_clear()
    encrypted = encrypt_text("Bearer extremely-secret-token")
    assert encrypted.startswith(PREFIX)
    assert "extremely-secret-token" not in encrypted
    assert decrypt_text(encrypted) == "Bearer extremely-secret-token"
    get_fernet.cache_clear()


def test_encrypted_sqlalchemy_types_hide_raw_transaction_values(monkeypatch):
    from app.core import encryption

    monkeypatch.setattr(encryption.settings, "data_encryption_key", Fernet.generate_key().decode())
    get_fernet.cache_clear()
    db_engine = create_engine("sqlite:///:memory:")
    HttpTransaction.__table__.create(db_engine)

    with Session(db_engine) as db:
        tx = HttpTransaction(
            project_id=1, method="POST", url="https://example.com/login",
            request_headers={"Authorization": "Bearer raw-secret"}, request_body='{"password":"hunter2"}',
            response_headers={"Set-Cookie": "session=raw-cookie"}, response_cookies=["session=raw-cookie"],
            response_body='{"token":"raw-response-token"}', technologies=[], interesting_indicators=[],
        )
        # Disable FK enforcement in this isolated type-level test.
        db.add(tx)
        db.commit()
        tx_id = tx.id

    with db_engine.connect() as connection:
        raw = connection.execute(text("SELECT request_headers, request_body, response_body FROM http_transactions WHERE id=:id"), {"id": tx_id}).one()
        assert all(str(value).startswith(PREFIX) for value in raw)
        assert "raw-secret" not in " ".join(map(str, raw))
        assert "hunter2" not in " ".join(map(str, raw))

    with Session(db_engine) as db:
        restored = db.get(HttpTransaction, tx_id)
        assert restored.request_headers["Authorization"] == "Bearer raw-secret"
        assert restored.request_body == '{"password":"hunter2"}'
        assert restored.response_body == '{"token":"raw-response-token"}'
    get_fernet.cache_clear()


def test_encrypted_types_read_legacy_plaintext():
    text_type = EncryptedText()
    json_type = EncryptedJSON()
    assert text_type.process_result_value("legacy body", None) == "legacy body"
    assert json_type.process_result_value('{"legacy":true}', None) == {"legacy": True}


def test_alembic_accepts_legacy_sqlite_storage_for_encrypted_types():
    sqlite_context = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    postgres_context = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    assert compare_encrypted_type(sqlite_context, None, None, JSON(), EncryptedJSON()) is False
    assert compare_encrypted_type(sqlite_context, None, None, Text(), EncryptedJSON()) is False
    assert compare_encrypted_type(sqlite_context, None, None, Text(), EncryptedText()) is False
    assert compare_encrypted_type(sqlite_context, None, None, Integer(), EncryptedJSON()) is None
    assert compare_encrypted_type(postgres_context, None, None, JSON(), EncryptedJSON()) is None
