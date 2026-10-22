"""PostgreSQL models owned by Execution."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from pytradekit.persistence.database import Base


class FillModel(Base):
    """Relational representation of an immutable Fill."""

    __tablename__ = "fills"
    __table_args__ = (
        UniqueConstraint("external_fill_id", name="uq_execution_external_fill_id"),
        {"schema": "execution"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    price_value: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    price_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    external_fill_id: Mapped[str | None] = mapped_column(String(200))
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    fee_currency: Mapped[str | None] = mapped_column(String(3))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
