"""PostgreSQL models for reconciliation evidence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from pytradekit.persistence.database import Base


class ReconciliationRunModel(Base):
    """Durable lifecycle and outcome of one reconciliation run."""

    __tablename__ = "runs"
    __table_args__ = (
        Index(
            "uq_reconciliation_active_account_scope",
            "account_id",
            "scope",
            unique=True,
            postgresql_where=text(
                "status IN ('CREATED','CAPTURING','COMPARING','RESOLVING','VERIFYING')"
            ),
        ),
        {"schema": "reconciliation"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    account_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    internal_watermark: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    broker_watermark: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    mismatch_count: Mapped[int] = mapped_column(Integer, nullable=False)
    critical_mismatch_count: Mapped[int] = mapped_column(Integer, nullable=False)
    result_status: Mapped[str | None] = mapped_column(String(32))
    state_confidence: Mapped[str | None] = mapped_column(String(32))
    correlation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class ReconciliationMismatchModel(Base):
    """Immutable mismatch evidence."""

    __tablename__ = "mismatches"
    __table_args__ = ({"schema": "reconciliation"},)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reconciliation.runs.id", name="fk_reconciliation_mismatches_run_id"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(300))
    internal_value_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    external_value_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReconciliationResolutionModel(Base):
    """Append-oriented recovery resolution evidence."""

    __tablename__ = "resolutions"
    __table_args__ = ({"schema": "reconciliation"},)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reconciliation.runs.id", name="fk_reconciliation_resolutions_run_id"),
        nullable=False,
    )
    mismatch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "reconciliation.mismatches.id",
            name="fk_reconciliation_resolutions_mismatch_id",
        ),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    correlation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
