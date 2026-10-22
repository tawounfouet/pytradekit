"""PostgreSQL engine and session infrastructure."""

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for PostgreSQL persistence models."""


def create_database_engine(
    database_url: str,
    *,
    echo: bool = False,
    require_tls: bool = False,
    connect_timeout_seconds: int = 5,
    statement_timeout_ms: int | None = None,
    pool_size: int = 5,
    max_overflow: int = 10,
) -> Engine:
    """Create a bounded PostgreSQL engine with explicit TLS expectations."""

    if not isinstance(database_url, str) or not database_url.strip():
        raise ValueError("Database URL must be a non-empty string.")
    if connect_timeout_seconds <= 0:
        raise ValueError("Database connect timeout must be positive.")
    if statement_timeout_ms is not None and statement_timeout_ms <= 0:
        raise ValueError("Database statement timeout must be positive.")
    if pool_size <= 0:
        raise ValueError("Database pool size must be positive.")
    if max_overflow < 0:
        raise ValueError("Database max overflow must be non-negative.")

    connect_args: dict[str, str | int] = {
        "connect_timeout": connect_timeout_seconds,
    }
    if require_tls:
        connect_args["sslmode"] = "require"
    if statement_timeout_ms is not None:
        connect_args["options"] = f"-c statement_timeout={statement_timeout_ms}"

    return create_engine(
        database_url.strip(),
        echo=echo,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        connect_args=connect_args,
    )


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
