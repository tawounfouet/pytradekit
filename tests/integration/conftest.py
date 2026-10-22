"""PostgreSQL integration fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from pytradekit.persistence.database import create_database_engine, create_session_factory


@pytest.fixture(scope="session")
def database_url() -> str:
    """Return the configured real PostgreSQL test URL."""
    value = os.environ.get("PYTRADEKIT_TEST_DATABASE_URL")
    if value is None:
        pytest.skip("PYTRADEKIT_TEST_DATABASE_URL is not configured.")
    return value


@pytest.fixture(scope="session")
def postgres_engine(database_url: str) -> Iterator[Engine]:
    """Migrate a real PostgreSQL database once for the integration suite."""
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    engine = create_database_engine(database_url)
    yield engine
    engine.dispose()
    command.downgrade(config, "base")


@pytest.fixture(scope="session")
def postgres_session_factory(
    postgres_engine: Engine,
) -> sessionmaker[Session]:
    """Return the canonical factory for committed integration transactions."""
    return create_session_factory(postgres_engine)


@pytest.fixture
def postgres_session(postgres_engine: Engine) -> Iterator[Session]:
    """Run one repository integration test inside an outer rollback transaction."""
    connection = postgres_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
