"""Architecture fitness functions for LOT-07 deployment hardening."""

from pathlib import Path

from tests.architecture._imports import python_sources

CONFIG = Path("src/pytradekit/runtime/configuration.py")
COMPOSE = Path("docker-compose.yml")
DOCKERFILE = Path("Dockerfile")
ALEMBIC = Path("alembic.ini")


def test_ff_047_0_7_cannot_enable_live_runtime() -> None:
    config = CONFIG.read_text(encoding="utf-8")
    authored = "\n".join(
        path.read_text(encoding="utf-8")
        for path in python_sources()
    )

    assert 'LIVE = "LIVE"' not in config
    assert "RuntimeEnvironment.LIVE" not in authored
    assert "https://api.alpaca.markets" not in authored


def test_compose_contains_only_secret_file_references() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")

    assert "POSTGRES_PASSWORD:" not in compose
    assert "ALPACA_PAPER_API_KEY:" not in compose
    assert "ALPACA_PAPER_SECRET_KEY:" not in compose
    assert "file:///run/secrets/" in compose
    assert "POSTGRES_PASSWORD_FILE" in compose


def test_container_runs_unprivileged_and_exposes_read_only_health() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    compose = COMPOSE.read_text(encoding="utf-8")

    assert "USER pytradekit" in dockerfile
    assert "/health/live" in dockerfile
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose


def test_alembic_configuration_contains_no_persisted_database_url() -> None:
    source = ALEMBIC.read_text(encoding="utf-8")

    assert "postgresql+psycopg://" not in source
    assert "sqlalchemy.url =" in source
