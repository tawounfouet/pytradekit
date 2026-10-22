"""Alembic environment for PyTradeKit PostgreSQL persistence."""

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from pytradekit.execution.adapters.postgres import models as execution_models
from pytradekit.orders.adapters.postgres import models as order_models
from pytradekit.persistence import message_models, runtime_models
from pytradekit.persistence.database import Base
from pytradekit.portfolio.adapters.postgres import models as portfolio_models
from pytradekit.reconciliation.adapters.postgres import models as reconciliation_models
from pytradekit.risk.adapters.postgres import models as risk_models
from pytradekit.runtime.adapters import build_default_secrets
from pytradekit.runtime.configuration import SecretRef

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_registered_models = (
    execution_models,
    order_models,
    portfolio_models,
    risk_models,
    message_models,
    runtime_models,
    reconciliation_models,
)
target_metadata = Base.metadata


def _database_url() -> str:
    reference = SecretRef(
        os.environ.get(
            "PYTRADEKIT_DATABASE_URL_REF",
            "env://PYTRADEKIT_DATABASE_URL",
        )
    )
    secret_root = Path(
        os.environ.get("PYTRADEKIT_SECRET_FILE_ROOT", "/run/secrets")
    )
    raw_url = build_default_secrets(file_root=secret_root).resolve(reference)
    require_tls = (
        os.environ.get("PYTRADEKIT_DATABASE_REQUIRE_TLS", "true")
        .strip()
        .lower()
        not in {"0", "false", "no"}
    )
    url = make_url(raw_url)
    if require_tls and url.query.get("sslmode") is None:
        url = url.update_query_dict({"sslmode": "require"})
    return url.render_as_string(hide_password=False)


def _configure_database_url() -> None:
    config.set_main_option(
        "sqlalchemy.url",
        _database_url().replace("%", "%%"),
    )


_configure_database_url()


def run_migrations_offline() -> None:
    """Run migrations without creating an Engine."""
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
    """Run migrations with a live Engine."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
