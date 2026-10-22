"""Governed kill-switch aggregate."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from pytradekit.safety.domain.ids import KillSwitchId
from pytradekit.security.domain import ActorId
from pytradekit.shared import DomainValidationError, require_utc_datetime


class KillSwitchState(StrEnum):
    """Kill-switch lifecycle state."""

    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"


class KillSwitchScope(StrEnum):
    """P0 kill-switch scope."""

    GLOBAL = "GLOBAL"
    ENVIRONMENT = "ENVIRONMENT"
    ACCOUNT = "ACCOUNT"
    STRATEGY = "STRATEGY"


@dataclass(frozen=True, slots=True)
class KillSwitch:
    """Persistent emergency containment state with optimistic versioning."""

    id: KillSwitchId
    state: KillSwitchState
    scope: KillSwitchScope
    reason: str
    activated_by: ActorId
    activated_at: datetime
    environment: str | None = None
    scope_id: str | None = None
    released_by: ActorId | None = None
    released_at: datetime | None = None
    release_reason: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.id, KillSwitchId):
            raise DomainValidationError("KillSwitch id is invalid.")
        if not isinstance(self.state, KillSwitchState):
            raise DomainValidationError("KillSwitch state is invalid.")
        if not isinstance(self.scope, KillSwitchScope):
            raise DomainValidationError("KillSwitch scope is invalid.")
        if not isinstance(self.activated_by, ActorId):
            raise DomainValidationError("KillSwitch activated_by is invalid.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise DomainValidationError("KillSwitch reason must be non-empty.")
        require_utc_datetime(self.activated_at, field_name="KillSwitch activated_at")
        if self.version < 1:
            raise DomainValidationError("KillSwitch version must be positive.")

        if self.scope is KillSwitchScope.GLOBAL:
            if self.environment is not None or self.scope_id is not None:
                raise DomainValidationError(
                    "GLOBAL KillSwitch cannot define environment or scope_id."
                )
        else:
            if not isinstance(self.environment, str) or not self.environment.strip():
                raise DomainValidationError(
                    "Non-global KillSwitch requires environment."
                )
            object.__setattr__(self, "environment", self.environment.strip())

        if self.scope in {KillSwitchScope.ACCOUNT, KillSwitchScope.STRATEGY}:
            if not isinstance(self.scope_id, str) or not self.scope_id.strip():
                raise DomainValidationError(
                    "ACCOUNT or STRATEGY KillSwitch requires scope_id."
                )
            object.__setattr__(self, "scope_id", self.scope_id.strip())
        elif self.scope is KillSwitchScope.ENVIRONMENT and self.scope_id is not None:
            raise DomainValidationError(
                "ENVIRONMENT KillSwitch cannot define scope_id."
            )

        if self.state is KillSwitchState.ACTIVE:
            if any(
                value is not None
                for value in (self.released_by, self.released_at, self.release_reason)
            ):
                raise DomainValidationError(
                    "ACTIVE KillSwitch cannot contain release evidence."
                )
        else:
            if (
                self.released_by is None
                or self.released_at is None
                or self.release_reason is None
            ):
                raise DomainValidationError(
                    "INACTIVE KillSwitch requires complete release evidence."
                )
            require_utc_datetime(
                self.released_at,
                field_name="KillSwitch released_at",
            )

    @property
    def active(self) -> bool:
        return self.state is KillSwitchState.ACTIVE

    def matches(
        self,
        *,
        environment: str,
        account_id: str,
        strategy_id: str | None,
    ) -> bool:
        """Return whether this switch governs the supplied action scope."""
        if not self.active:
            return False
        if self.scope is KillSwitchScope.GLOBAL:
            return True
        if self.environment != environment:
            return False
        if self.scope is KillSwitchScope.ENVIRONMENT:
            return True
        if self.scope is KillSwitchScope.ACCOUNT:
            return self.scope_id == account_id
        return strategy_id is not None and self.scope_id == strategy_id

    def release(
        self,
        *,
        actor_id: ActorId,
        reason: str,
        occurred_at: datetime,
    ) -> "KillSwitch":
        """Release this blocker without manufacturing trading readiness."""
        if not self.active:
            return self
        if not isinstance(reason, str) or not reason.strip():
            raise DomainValidationError("KillSwitch release reason must be non-empty.")
        timestamp = require_utc_datetime(
            occurred_at,
            field_name="KillSwitch release time",
        )
        if timestamp < self.activated_at:
            raise DomainValidationError(
                "KillSwitch release cannot precede activation."
            )
        return replace(
            self,
            state=KillSwitchState.INACTIVE,
            released_by=actor_id,
            released_at=timestamp,
            release_reason=reason.strip(),
            version=self.version + 1,
        )
