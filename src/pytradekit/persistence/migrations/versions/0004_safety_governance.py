"""Create milestone 0.7 safety governance persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_safety_governance"
down_revision: str | None = "0003_security_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS safety"))
    op.create_table(
        "kill_switches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("environment", sa.String(32)),
        sa.Column("scope_id", sa.String(200)),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("activated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_by", postgresql.UUID(as_uuid=True)),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("release_reason", sa.String(1000)),
        sa.Column("version", sa.Integer(), nullable=False),
        schema="safety",
    )
    op.create_index(
        "ix_safety_kill_switch_scope",
        "kill_switches",
        ["scope"],
        schema="safety",
    )
    op.create_index(
        "ix_safety_kill_switch_environment",
        "kill_switches",
        ["environment"],
        schema="safety",
    )
    op.create_index(
        "ix_safety_kill_switch_scope_id",
        "kill_switches",
        ["scope_id"],
        schema="safety",
    )

    op.create_table(
        "risk_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("account_id", sa.String(200), nullable=False),
        sa.Column("strategy_id", sa.String(200)),
        sa.Column("risk_rule", sa.String(200)),
        sa.Column("instrument_id", sa.String(200)),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        schema="safety",
    )
    op.create_index(
        "ix_safety_risk_override_status",
        "risk_overrides",
        ["status"],
        schema="safety",
    )
    op.create_index(
        "ix_safety_risk_override_account",
        "risk_overrides",
        ["account_id"],
        schema="safety",
    )

    op.create_table(
        "confirmations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("scope_reference", sa.String(300), nullable=False),
        sa.Column("challenge_reference", sa.String(300), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("process_nonce", sa.String(200), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        schema="safety",
    )
    op.create_index(
        "ix_safety_confirmation_process_nonce",
        "confirmations",
        ["process_nonce"],
        schema="safety",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_safety_confirmation_process_nonce",
        table_name="confirmations",
        schema="safety",
    )
    op.drop_table("confirmations", schema="safety")
    op.drop_index(
        "ix_safety_risk_override_account",
        table_name="risk_overrides",
        schema="safety",
    )
    op.drop_index(
        "ix_safety_risk_override_status",
        table_name="risk_overrides",
        schema="safety",
    )
    op.drop_table("risk_overrides", schema="safety")
    op.drop_index(
        "ix_safety_kill_switch_scope_id",
        table_name="kill_switches",
        schema="safety",
    )
    op.drop_index(
        "ix_safety_kill_switch_environment",
        table_name="kill_switches",
        schema="safety",
    )
    op.drop_index(
        "ix_safety_kill_switch_scope",
        table_name="kill_switches",
        schema="safety",
    )
    op.drop_table("kill_switches", schema="safety")
    op.execute(sa.text("DROP SCHEMA IF EXISTS safety"))
