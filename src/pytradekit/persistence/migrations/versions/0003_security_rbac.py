"""Create milestone 0.7 security RBAC tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_security_rbac"
down_revision: str | None = "0002_reconciliation_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS security"))
    op.create_table(
        "actors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        schema="security",
    )
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        schema="security",
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("security.roles.id", name="fk_security_role_permissions_role_id"),
                  primary_key=True),
        sa.Column("permission", sa.String(64), primary_key=True),
        schema="security",
    )
    op.create_table(
        "role_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("security.actors.id", name="fk_security_role_assignments_actor_id"),
                  nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("security.roles.id", name="fk_security_role_assignments_role_id"),
                  nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("account_scope", sa.String(32), nullable=False),
        sa.Column("account_id", sa.String(200)),
        sa.Column("operation_scope", sa.String(32), nullable=False),
        sa.Column("operation", sa.String(64)),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("security.actors.id", name="fk_security_role_assignments_assigned_by"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="security",
    )
    op.create_index("ix_security_role_assignments_actor_id", "role_assignments", ["actor_id"], schema="security")
    op.create_index("ix_security_role_assignments_role_id", "role_assignments", ["role_id"], schema="security")


def downgrade() -> None:
    op.drop_index("ix_security_role_assignments_role_id", table_name="role_assignments", schema="security")
    op.drop_index("ix_security_role_assignments_actor_id", table_name="role_assignments", schema="security")
    op.drop_table("role_assignments", schema="security")
    op.drop_table("role_permissions", schema="security")
    op.drop_table("roles", schema="security")
    op.drop_table("actors", schema="security")
    op.execute(sa.text("DROP SCHEMA IF EXISTS security"))
