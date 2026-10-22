"""Create milestone 0.6 reconciliation evidence tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_reconciliation_evidence"
down_revision: str | None = "0001_persistence_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the reconciliation evidence schema."""

    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS reconciliation"))
    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("trigger", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("internal_watermark", postgresql.JSONB()),
        sa.Column("broker_watermark", postgresql.JSONB()),
        sa.Column("mismatch_count", sa.Integer(), nullable=False),
        sa.Column("critical_mismatch_count", sa.Integer(), nullable=False),
        sa.Column("result_status", sa.String(32)),
        sa.Column("state_confidence", sa.String(32)),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        schema="reconciliation",
    )
    op.create_index(
        "uq_reconciliation_active_account_scope",
        "runs",
        ["account_id", "scope"],
        unique=True,
        schema="reconciliation",
        postgresql_where=sa.text(
            "status IN ('CREATED','CAPTURING','COMPARING','RESOLVING','VERIFYING')"
        ),
    )
    op.create_table(
        "mismatches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "reconciliation.runs.id",
                name="fk_reconciliation_mismatches_run_id",
            ),
            nullable=False,
        ),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(300)),
        sa.Column("internal_value_json", postgresql.JSONB()),
        sa.Column("external_value_json", postgresql.JSONB()),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        schema="reconciliation",
    )
    op.create_table(
        "resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "reconciliation.runs.id",
                name="fk_reconciliation_resolutions_run_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "mismatch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "reconciliation.mismatches.id",
                name="fk_reconciliation_resolutions_mismatch_id",
            ),
            nullable=False,
        ),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("verification_json", postgresql.JSONB()),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        schema="reconciliation",
    )


def downgrade() -> None:
    """Drop milestone 0.6 reconciliation evidence tables."""

    op.drop_table("resolutions", schema="reconciliation")
    op.drop_table("mismatches", schema="reconciliation")
    op.drop_index(
        "uq_reconciliation_active_account_scope",
        table_name="runs",
        schema="reconciliation",
    )
    op.drop_table("runs", schema="reconciliation")
    op.execute(sa.text("DROP SCHEMA IF EXISTS reconciliation"))
