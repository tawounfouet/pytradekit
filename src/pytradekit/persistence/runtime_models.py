"""Cross-cutting runtime persistence models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from pytradekit.persistence.database import Base


class RuntimeMetadataModel(Base):
    """Durable runtime metadata entry."""

    __tablename__ = "metadata"
    __table_args__ = {"schema": "runtime"}

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BrokerMappingModel(Base):
    """Durable mapping between canonical and provider identities."""

    __tablename__ = "broker_mappings"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "mapping_type",
            "external_id",
            name="uq_runtime_broker_mapping_external",
        ),
        {"schema": "runtime"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    mapping_type: Mapped[str] = mapped_column(String(100), nullable=False)
    canonical_id: Mapped[str] = mapped_column(String(200), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
