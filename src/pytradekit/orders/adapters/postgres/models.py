"""PostgreSQL models owned by Orders."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from pytradekit.persistence.database import Base


class OrderModel(Base):
    """Relational representation of the Order aggregate."""

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("client_order_id", name="uq_orders_client_order_id"),
        {"schema": "orders"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    instrument_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    time_in_force: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    limit_price_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    limit_price_currency: Mapped[str | None] = mapped_column(String(3))
    client_order_id: Mapped[str | None] = mapped_column(String(200))
    external_order_id: Mapped[str | None] = mapped_column(String(200))
    execution_certainty: Mapped[str] = mapped_column(String(16), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))
    failure_reason: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cancel_previous_status: Mapped[str | None] = mapped_column(String(32))
    processed_fill_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
