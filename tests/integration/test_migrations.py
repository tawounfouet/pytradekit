"""Alembic migration qualification against PostgreSQL."""

from sqlalchemy import Engine, inspect


def test_fresh_database_contains_persistence_schemas(postgres_engine: Engine) -> None:
    inspector = inspect(postgres_engine)

    assert "orders" in inspector.get_schema_names()
    assert "execution" in inspector.get_schema_names()
    assert "portfolio" in inspector.get_schema_names()
    assert "risk" in inspector.get_schema_names()
    assert "runtime" in inspector.get_schema_names()
    assert "reconciliation" in inspector.get_schema_names()
    assert "security" in inspector.get_schema_names()
    assert "safety" in inspector.get_schema_names()

    assert "orders" in inspector.get_table_names(schema="orders")
    assert "fills" in inspector.get_table_names(schema="execution")
    assert "positions" in inspector.get_table_names(schema="portfolio")
    assert "balances" in inspector.get_table_names(schema="portfolio")
    assert "policies" in inspector.get_table_names(schema="risk")
    assert "metadata" in inspector.get_table_names(schema="runtime")
    assert "outbox" in inspector.get_table_names(schema="runtime")
    assert "inbox" in inspector.get_table_names(schema="runtime")
    assert "runs" in inspector.get_table_names(schema="reconciliation")
    assert "mismatches" in inspector.get_table_names(schema="reconciliation")
    assert "resolutions" in inspector.get_table_names(schema="reconciliation")
    assert "actors" in inspector.get_table_names(schema="security")
    assert "roles" in inspector.get_table_names(schema="security")
    assert "role_permissions" in inspector.get_table_names(schema="security")
    assert "role_assignments" in inspector.get_table_names(schema="security")
    assert "kill_switches" in inspector.get_table_names(schema="safety")
    assert "risk_overrides" in inspector.get_table_names(schema="safety")
    assert "confirmations" in inspector.get_table_names(schema="safety")
