from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_security(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA secure_delete=ON")
        cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models so they register on Base.metadata before create_all.
    from app.auth import models as _auth_models  # noqa: F401
    from app.evidence import models as _evidence_models  # noqa: F401
    from app.diff import models as _diff_models  # noqa: F401
    from app.http import models as _http_models  # noqa: F401
    from app.identities import models as _identity_models  # noqa: F401
    from app.investigations import models as _investigations_models  # noqa: F401
    from app.js_inspector import models as _js_inspector_models  # noqa: F401
    from app.projects import models as _projects_models  # noqa: F401
    from app.recon import models as _recon_models  # noqa: F401
    from app.reports import models as _reports_models  # noqa: F401
    from app.scopeguard import models as _scopeguard_models  # noqa: F401
    from app.surface import models as _surface_models  # noqa: F401

    _add_legacy_project_owner_column()
    Base.metadata.create_all(bind=engine)
    _add_legacy_identity_profile_columns()
    _add_legacy_scenario_investigation_columns()
    _add_legacy_auth_session_columns()
    _add_legacy_recon_queue_column()
    _add_legacy_asset_sources_column()
    _add_legacy_dns_records_column()
    _add_legacy_probe_source_column()
    _encrypt_legacy_http_transactions()
    _purge_expired_http_transactions()


def _alembic_config():
    from pathlib import Path
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    return config


def database_health() -> dict:
    """For GET /api/health - is the DB reachable and at the latest migration?"""
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    try:
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
    except Exception as exc:  # noqa: BLE001
        return {"reachable": False, "error": str(exc)[:200], "migrations": "unknown"}

    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    return {
        "reachable": True,
        "migrations": "up_to_date" if current == head else "behind",
        "current_revision": current,
        "head_revision": head,
    }


def migrate_database() -> None:
    """Upgrade a fresh database or safely adopt a pre-Alembic database."""
    from alembic import command

    config = _alembic_config()

    table_names = set(inspect(engine).get_table_names())
    if "projects" in table_names and "alembic_version" not in table_names:
        # One-time bridge for installations created by Base.create_all().
        # Bring their schema to the baseline shape, preserve all rows, then
        # mark that baseline as applied. Future upgrades are Alembic-only.
        init_db()
        command.stamp(config, "head")
    else:
        command.upgrade(config, "head")
        _encrypt_legacy_http_transactions()
        _purge_expired_http_transactions()


def _add_legacy_project_owner_column() -> None:
    """Small compatibility bridge until the Alembic milestone lands."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        exists = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"))
        if exists.first() is None:
            return
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(projects)"))}
        if "owner_id" not in columns:
            connection.execute(text("ALTER TABLE projects ADD COLUMN owner_id INTEGER REFERENCES users(id)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_projects_owner_id ON projects(owner_id)"))


def _add_legacy_auth_session_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "user_sessions" not in tables:
            return
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(user_sessions)"))}
        if "ip_address" not in columns:
            connection.execute(text("ALTER TABLE user_sessions ADD COLUMN ip_address VARCHAR(64) NOT NULL DEFAULT ''"))
        if "user_agent" not in columns:
            connection.execute(text("ALTER TABLE user_sessions ADD COLUMN user_agent VARCHAR(500) NOT NULL DEFAULT ''"))


def _add_legacy_recon_queue_column() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "recon_jobs" not in tables:
            return
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(recon_jobs)"))}
        if "queue_job_id" not in columns:
            connection.execute(text("ALTER TABLE recon_jobs ADD COLUMN queue_job_id VARCHAR(100)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_recon_jobs_queue_job_id ON recon_jobs(queue_job_id)"))


def _add_legacy_asset_sources_column() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "assets" not in tables:
            return
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(assets)"))}
        if "discovery_sources" not in columns:
            connection.execute(text("ALTER TABLE assets ADD COLUMN discovery_sources JSON NOT NULL DEFAULT '[]'"))


def _add_legacy_dns_records_column() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "assets" not in tables:
            return
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(assets)"))}
        if "dns_records" not in columns:
            connection.execute(text("ALTER TABLE assets ADD COLUMN dns_records JSON NOT NULL DEFAULT '{}'"))


def _add_legacy_probe_source_column() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "assets" not in tables:
            return
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(assets)"))}
        if "probe_source" not in columns:
            connection.execute(text("ALTER TABLE assets ADD COLUMN probe_source VARCHAR(50) NOT NULL DEFAULT 'vajra-httpx'"))


def _add_legacy_identity_profile_columns() -> None:
    """Complete pre-Alembic HTTP tables before they are stamped at head."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "http_transactions" not in tables or "identity_profiles" not in tables:
            return
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(http_transactions)"))}
        if "identity_profile_id" not in columns:
            connection.execute(text(
                "ALTER TABLE http_transactions ADD COLUMN identity_profile_id INTEGER "
                "REFERENCES identity_profiles(id) ON DELETE SET NULL"
            ))
        if "identity_profile_key" not in columns:
            connection.execute(text("ALTER TABLE http_transactions ADD COLUMN identity_profile_key VARCHAR(64)"))
        if "identity_profile_name" not in columns:
            connection.execute(text("ALTER TABLE http_transactions ADD COLUMN identity_profile_name VARCHAR(100)"))
        if "profile_header_names" not in columns:
            connection.execute(text(
                "ALTER TABLE http_transactions ADD COLUMN profile_header_names JSON NOT NULL DEFAULT '[]'"
            ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_http_transactions_identity_profile_id "
            "ON http_transactions(identity_profile_id)"
        ))


def _add_legacy_scenario_investigation_columns() -> None:
    """Add scenario traceability to pre-Alembic investigation tables."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "investigations" not in tables or "access_control_scenarios" not in tables:
            return
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(investigations)"))}
        if "access_control_scenario_id" not in columns:
            connection.execute(text(
                "ALTER TABLE investigations ADD COLUMN access_control_scenario_id INTEGER "
                "REFERENCES access_control_scenarios(id) ON DELETE SET NULL"
            ))
        if "access_control_snapshot" not in columns:
            connection.execute(text(
                "ALTER TABLE investigations ADD COLUMN access_control_snapshot JSON NOT NULL DEFAULT '{}'"
            ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_investigations_access_control_scenario_id "
            "ON investigations(access_control_scenario_id)"
        ))


def _encrypt_legacy_http_transactions() -> None:
    """Rewrite pre-encryption SQLite transaction payloads in place.

    PostgreSQL installations created with the encrypted model already use
    TEXT columns. This compatibility migration is specifically for the
    development SQLite database that predates encrypted field types.
    """
    if engine.dialect.name != "sqlite":
        return
    from app.core.encryption import PREFIX, encrypt_text

    columns = ("request_headers", "request_body", "response_headers", "response_cookies", "response_body")
    with engine.begin() as connection:
        rows = connection.execute(text(f"SELECT id, {', '.join(columns)} FROM http_transactions")).mappings()
        for row in rows:
            updates = {
                column: encrypt_text(row[column])
                for column in columns
                if row[column] is not None and not str(row[column]).startswith(PREFIX)
            }
            if updates:
                assignments = ", ".join(f"{column} = :{column}" for column in updates)
                connection.execute(
                    text(f"UPDATE http_transactions SET {assignments} WHERE id = :transaction_id"),
                    {**updates, "transaction_id": row["id"]},
                )


def _purge_expired_http_transactions() -> int:
    """Delete expired raw transactions on startup; zero disables retention."""
    from datetime import datetime, timedelta, timezone
    from app.http.models import HttpTransaction

    days = settings.transaction_retention_days
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with SessionLocal() as db:
        deleted = db.query(HttpTransaction).filter(HttpTransaction.created_at < cutoff).delete(synchronize_session=False)
        db.commit()
        return deleted
