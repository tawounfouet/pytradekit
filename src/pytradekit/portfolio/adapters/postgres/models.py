"""PostgreSQL models owned by Portfolio."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import ClassVar
from uuid import UUID

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from pytradekit.persistence.database import Base


class AccountModel(Base):
    """Relational account identity used by portfolio state."""

    __tablename__ = "accounts"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "portfolio"}

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))


class PositionModel(Base):
    """Relational representation of a portfolio Position."""

    __tablename__ = "positions"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "portfolio"}

    account_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    instrument_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    average_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class BalanceModel(Base):
    """Relational representation of a portfolio Balance."""

    __tablename__ = "balances"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "portfolio"}

    account_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    cash: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    available: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    reserved: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class ProcessedFillModel(Base):
    """Durable portfolio fill idempotency key."""

    __tablename__ = "processed_fills"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "portfolio"}

    fill_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
