"""Controlled time-bound risk-policy override aggregate."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from pytradekit.safety.domain.ids import RiskOverrideId
from pytradekit.security.domain import ActorId
from pytradekit.shared import (
    CorrelationId,
    DomainValidationError,
    require_utc_datetime,
)


class RiskOverrideStatus(StrEnum):
    """Lifecycle of a risk-policy exception."""

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class RiskOverrideScope:
    """Scope of one risk exception."""

    account_id: str
    strategy_id: str | None = None
    risk_rule: str | None = None
    instrument_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, str) or not self.account_id.strip():
            raise DomainValidationError("RiskOverrideScope account_id is required.")
        object.__setattr__(self, "account_id", self.account_id.strip())
        for field_name in ("strategy_id", "risk_rule", "instrument_id"):
            value = getattr(self, field_name)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise DomainValidationError(
                        f"RiskOverrideScope {field_name} must be non-empty."
                    )
                object.__setattr__(self, field_name, value.strip())

    def matches(
        self,
        *,
        account_id: str,
        strategy_id: str | None,
        risk_rule_codes: tuple[str, ...],
        instrument_id: str,
    ) -> bool:
        if self.account_id != account_id:
            return False
        if self.strategy_id is not None and self.strategy_id != strategy_id:
            return False
        if self.risk_rule is not None and self.risk_rule not in risk_rule_codes:
            return False
        return self.instrument_id is None or self.instrument_id == instrument_id


@dataclass(frozen=True, slots=True)
class RiskOverride:
    """Versioned, expiring exception to configured risk constraints only."""

    id: RiskOverrideId
    scope: RiskOverrideScope
    reason: str
    requested_by: ActorId
    created_at: datetime
    valid_from: datetime
    valid_until: datetime
    correlation_id: CorrelationId
    status: RiskOverrideStatus = RiskOverrideStatus.PENDING
    approved_by: ActorId | None = None
    approved_at: datetime | None = None
    revoked_by: ActorId | None = None
    revoked_at: datetime | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.id, RiskOverrideId):
            raise DomainValidationError("RiskOverride id is invalid.")
        if not isinstance(self.scope, RiskOverrideScope):
            raise DomainValidationError("RiskOverride scope is invalid.")
        if not isinstance(self.requested_by, ActorId):
            raise DomainValidationError("RiskOverride requested_by is invalid.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise DomainValidationError("RiskOverride reason must be non-empty.")
        require_utc_datetime(self.created_at, field_name="RiskOverride created_at")
        require_utc_datetime(self.valid_from, field_name="RiskOverride valid_from")
        require_utc_datetime(self.valid_until, field_name="RiskOverride valid_until")
        if self.valid_until <= self.valid_from:
            raise DomainValidationError(
                "RiskOverride valid_until must be after valid_from."
            )
        if self.version < 1:
            raise DomainValidationError("RiskOverride version must be positive.")

    def effective_status(self, at: datetime) -> RiskOverrideStatus:
        """Derive expiry without mutating persisted truth."""
        now = require_utc_datetime(at, field_name="RiskOverride evaluation time")
        if self.status is RiskOverrideStatus.ACTIVE and now >= self.valid_until:
            return RiskOverrideStatus.EXPIRED
        return self.status

    def is_active(self, at: datetime) -> bool:
        now = require_utc_datetime(at, field_name="RiskOverride evaluation time")
        return (
            self.status is RiskOverrideStatus.ACTIVE
            and self.valid_from <= now < self.valid_until
        )

    def approve(
        self,
        *,
        actor_id: ActorId,
        occurred_at: datetime,
    ) -> "RiskOverride":
        if self.status is not RiskOverrideStatus.PENDING:
            raise DomainValidationError("Only PENDING RiskOverride can be approved.")
        now = require_utc_datetime(
            occurred_at,
            field_name="RiskOverride approval time",
        )
        if now >= self.valid_until:
            raise DomainValidationError("Expired RiskOverride cannot be approved.")
        return replace(
            self,
            status=RiskOverrideStatus.ACTIVE,
            approved_by=actor_id,
            approved_at=now,
            version=self.version + 1,
        )

    def revoke(
        self,
        *,
        actor_id: ActorId,
        occurred_at: datetime,
    ) -> "RiskOverride":
        if self.status not in {
            RiskOverrideStatus.PENDING,
            RiskOverrideStatus.ACTIVE,
        }:
            return self
        now = require_utc_datetime(
            occurred_at,
            field_name="RiskOverride revocation time",
        )
        return replace(
            self,
            status=RiskOverrideStatus.REVOKED,
            revoked_by=actor_id,
            revoked_at=now,
            version=self.version + 1,
        )
