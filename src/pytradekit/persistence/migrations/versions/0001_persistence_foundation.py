"""Create milestone 0.5 persistence foundation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_persistence_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create schemas and durable state tables."""
    for schema in ("orders", "execution", "portfolio", "risk", "runtime"):
        op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("side", sa.String(16), nullable=False),
        sa.Column("order_type", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(38, 18), nullable=False),
        sa.Column("time_in_force", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("filled_quantity", sa.Numeric(38, 18), nullable=False),
        sa.Column("limit_price_value", sa.Numeric(38, 18)),
        sa.Column("limit_price_currency", sa.String(3)),
        sa.Column("client_order_id", sa.String(200)),
        sa.Column("external_order_id", sa.String(200)),
        sa.Column("execution_certainty", sa.String(16), nullable=False),
        sa.Column("rejection_reason", sa.String(1000)),
        sa.Column("failure_reason", sa.String(1000)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("cancel_previous_status", sa.String(32)),
        sa.Column("processed_fill_ids", postgresql.JSONB(), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("client_order_id", name="uq_orders_client_order_id"),
        schema="orders",
    )

    op.create_table(
        "fills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(38, 18), nullable=False),
        sa.Column("price_value", sa.Numeric(38, 18), nullable=False),
        sa.Column("price_currency", sa.String(3), nullable=False),
        sa.Column("external_fill_id", sa.String(200)),
        sa.Column("fee_amount", sa.Numeric(38, 18)),
        sa.Column("fee_currency", sa.String(3)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("external_fill_id", name="uq_execution_external_fill_id"),
        schema="execution",
    )
    op.create_index(
        "ix_execution_fills_order_id",
        "fills",
        ["order_id"],
        schema="execution",
    )

    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("name", sa.String(200)),
        schema="portfolio",
    )
    op.create_table(
        "positions",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("quantity", sa.Numeric(38, 18), nullable=False),
        sa.Column("average_price", sa.Numeric(38, 18)),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(38, 18), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        schema="portfolio",
    )
    op.create_table(
        "balances",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("currency", sa.String(3), primary_key=True),
        sa.Column("cash", sa.Numeric(38, 18), nullable=False),
        sa.Column("available", sa.Numeric(38, 18)),
        sa.Column("reserved", sa.Numeric(38, 18)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False),
        schema="portfolio",
    )
    op.create_table(
        "processed_fills",
        sa.Column("fill_key", sa.String(300), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        schema="portfolio",
    )

    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("scope_id", sa.String(200)),
        sa.Column("limits", postgresql.JSONB(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("allow_reduce_only_when_halted", sa.Boolean(), nullable=False),
        schema="risk",
    )
    op.create_index("ix_risk_policies_scope", "policies", ["scope"], schema="risk")
    op.create_index("ix_risk_policies_scope_id", "policies", ["scope_id"], schema="risk")

    op.create_table(
        "metadata",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="runtime",
    )
    op.create_table(
        "broker_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("mapping_type", sa.String(100), nullable=False),
        sa.Column("canonical_id", sa.String(200), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "provider",
            "mapping_type",
            "external_id",
            name="uq_runtime_broker_mapping_external",
        ),
        schema="runtime",
    )


def downgrade() -> None:
    """Drop milestone 0.5 persistence foundation."""
    op.drop_table("broker_mappings", schema="runtime")
    op.drop_table("metadata", schema="runtime")
    op.drop_index("ix_risk_policies_scope_id", table_name="policies", schema="risk")
    op.drop_index("ix_risk_policies_scope", table_name="policies", schema="risk")
    op.drop_table("policies", schema="risk")
    op.drop_table("processed_fills", schema="portfolio")
    op.drop_table("balances", schema="portfolio")
    op.drop_table("positions", schema="portfolio")
    op.drop_table("accounts", schema="portfolio")
    op.drop_index("ix_execution_fills_order_id", table_name="fills", schema="execution")
    op.drop_table("fills", schema="execution")
    op.drop_table("orders", schema="orders")

    for schema in ("runtime", "risk", "portfolio", "execution", "orders"):
        op.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema}"))
