"""Scoped trading halt state."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Self
from uuid import UUID, uuid4

from pytradekit.risk.domain.risk_scope import RiskScope
from pytradekit.shared import DomainValidationError, require_utc_datetime


@dataclass(frozen=True, slots=True)
class TradingHaltId:
    """UUID-backed trading halt identity."""

    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise DomainValidationError("TradingHaltId value must be a UUID.")

    @classmethod
    def new(cls) -> Self:
        return cls(uuid4())


@dataclass(frozen=True, slots=True)
class TradingHalt:
    """Immutable scoped halt that blocks risk-increasing activity."""

    id: TradingHaltId
    scope: RiskScope
    scope_id: str | None
    reason: str
    triggered_at: datetime
    released_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.scope not in {RiskScope.GLOBAL, RiskScope.ACCOUNT, RiskScope.STRATEGY}:
            raise DomainValidationError(
                "TradingHalt scope must be GLOBAL, ACCOUNT, or STRATEGY."
            )
        if self.scope is RiskScope.GLOBAL and self.scope_id is not None:
            raise DomainValidationError("GLOBAL TradingHalt must not define scope_id.")
        if self.scope is not RiskScope.GLOBAL:
            if self.scope_id is None or not self.scope_id.strip():
                raise DomainValidationError(
                    "Non-global TradingHalt requires a non-empty scope_id."
                )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise DomainValidationError("TradingHalt reason must be a non-empty string.")
        require_utc_datetime(self.triggered_at, field_name="TradingHalt triggered_at")
        if self.released_at is not None:
            released = require_utc_datetime(
                self.released_at,
                field_name="TradingHalt released_at",
            )
            if released < self.triggered_at:
                raise DomainValidationError(
                    "TradingHalt released_at cannot precede triggered_at."
                )

    @property
    def active(self) -> bool:
        return self.released_at is None

    def release(self, *, occurred_at: datetime) -> TradingHalt:
        timestamp = require_utc_datetime(occurred_at, field_name="TradingHalt release time")
        if timestamp < self.triggered_at:
            raise DomainValidationError(
                "TradingHalt release time cannot precede triggered_at."
            )
        if not self.active:
            return self
        return replace(self, released_at=timestamp)
