from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from app.core.database import Base
from app.core.encrypted_types import compare_encrypted_type

# Register every mapped model before exposing metadata to Alembic.
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

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
x_args = context.get_x_argument(as_dictionary=True)
if x_args.get("db_url"):
    config.set_main_option("sqlalchemy.url", x_args["db_url"])

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=compare_encrypted_type,
            render_as_batch=connection.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
