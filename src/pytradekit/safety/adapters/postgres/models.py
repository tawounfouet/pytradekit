"""PostgreSQL models owned by Safety."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from pytradekit.persistence.database import Base


class KillSwitchModel(Base):
    __tablename__ = "kill_switches"
    __table_args__ = ({"schema": "safety"},)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    environment: Mapped[str | None] = mapped_column(String(32), index=True)
    scope_id: Mapped[str | None] = mapped_column(String(200), index=True)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    activated_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class RiskOverrideModel(Base):
    __tablename__ = "risk_overrides"
    __table_args__ = ({"schema": "safety"},)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    strategy_id: Mapped[str | None] = mapped_column(String(200), index=True)
    risk_rule: Mapped[str | None] = mapped_column(String(200), index=True)
    instrument_id: Mapped[str | None] = mapped_column(String(200), index=True)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    requested_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    approved_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class DangerousActionConfirmationModel(Base):
    __tablename__ = "confirmations"
    __table_args__ = ({"schema": "safety"},)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_reference: Mapped[str] = mapped_column(String(300), nullable=False)
    challenge_reference: Mapped[str] = mapped_column(String(300), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    process_nonce: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
