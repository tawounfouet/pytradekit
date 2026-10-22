"""PostgreSQL models owned by Risk."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from pytradekit.persistence.database import Base


class RiskPolicyModel(Base):
    """Relational representation of a versioned RiskPolicy."""

    __tablename__ = "policies"
    __table_args__ = ({"schema": "risk"},)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_id: Mapped[str | None] = mapped_column(String(200), index=True)
    limits: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    allow_reduce_only_when_halted: Mapped[bool] = mapped_column(Boolean, nullable=False)
