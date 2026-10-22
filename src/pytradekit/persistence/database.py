"""PostgreSQL engine and session infrastructure."""

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for PostgreSQL persistence models."""


def create_database_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create a PostgreSQL engine with connection pre-ping enabled."""
    if not isinstance(database_url, str) or not database_url.strip():
        raise ValueError("Database URL must be a non-empty string.")
    return create_engine(database_url.strip(), echo=echo, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the canonical SQLAlchemy session factory."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def database_is_healthy(engine: Engine) -> bool:
    """Return whether a simple database probe succeeds."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True
